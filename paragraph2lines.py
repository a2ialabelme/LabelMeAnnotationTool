# -*- coding: utf-8 -*-

##
# @author RM
# @brief  Line detection on handwritten text, from full page, maybe not the best thing to do...
# @date   September 2015

import sys, os
import string, re
from xml.etree.cElementTree import Element, SubElement, Comment, tostring, ElementTree
import xml.etree.ElementTree as ET
import xml.etree.cElementTree as et
import unicodedata
import fnmatch
from random import randrange
import shutil
import itertools
import numpy
from bisect import bisect_right
from math import floor

#from scipy import ndimage

### A2ia stuff
import bridgeWithA2iACode

import PyCore

import PyImageProcessing as PyImp
import PyImageIO
import PyX_Kernel as PyX
import PyNeuralNetwork as PyNN
import TextReaderCommons as TRC
import PyHLC

import PyLib.HLC.TextProcessingBricks.TextLineDetector as TLD

import PyExternTools.Kaldi as PyKaldi

import PyDevGUI
if PyDevGUI.GetWin() is not None:
   PyDevGUI.DevGUI_SetKobWindow(0)
###

# USE PIL:
import ImageFont, ImageDraw, Image, ImageFilter, ImageOps, ImageChops

# pretty-writing of xml stuff
sys.path.append(src_topLevelPath+'/SetupProducts/RTeam/BNF')
from xmltools import indent

from FstRecognizer_RNNKaldi import CreateContainerFromWords

# stop bothering us with ascii crap
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import PyDevGUI
if PyDevGUI.GetWin() is not None:
   PyDevGUI.DevGUI_SetKobWindow(0)

# very ad-hoc function, with hard-coded blank string...
# TODO make this more flexible
def getBestRNNOut(opticalResult, mylabels):
   s = opticalResult.GetFramewiseProbasBeforePriors()
   c = opticalResult.GetFramewiseCosts()
   mat = numpy.array(s.tolist())
   mat.resize(s.SizeDim1(), s.SizeFeatures())
   chars = [mylabels[k] for k in mat.argmax(1)]
   #print "chars", chars
   cost = 0
   for k,i in enumerate(mat.argmax(1)):
      cost += c[k][i]

   decod = u""
   prev = '__blank__'

   for ch in chars:
      ch = unicode(ch, 'utf-8')
      if ch != prev:
         if ch != '__blank__':
            decod += ch
         prev = ch
   if len(decod) >= 1:
      cost = cost/float(len(decod))
   else:
      cost = 10000.0
   return decod, cost

def getBestRNNOutLM(alg):
   prev = PyNN.NN3_Label.GetReservedBlankId()
   decod = u""
   for ch in alg:
      ch = unicode(ch, 'utf-8')
      if ch != prev:
         if ch != PyNN.NN3_Label.GetReservedBlankId():
            decod += ch
         prev = ch
   return decod

# select candidate lines from the RNN output on each detected line, there are two thresholds:
# one on the number of characters recognized (to avoid spurious detection of lines)
# other on the average frame cost
def getRNNRecoOnLines(segmentation, trans_model, decode_fst, asc, decoder_opts):
   hyplines = []
   newSegmentation = []
   for segment in sorted(segmentation, key=lambda res: res.loc_zone.top):
   #origSegment = PyX.UtilsExtr_results_Factory(grp, origImg, 1., 0., 0., 0, 0, 0, segment.loc_zone)
      top = segment.loc_zone.top
      left = segment.loc_zone.left
      bottom = segment.loc_zone.bottom
      right = segment.loc_zone.right
      txt = ''
      cost = 10000.
      if (right-left) > minW and (bottom - top) > minH:
         try:
            origImg = PyHLC.GeoRefImage_FromUtilsImg(segment.extr_img) #PyHLC.GeoRefImage_FromUtilsImg(PyX.Utils_img_copy_img_zone_with_white_bound_nobug(pimage, segment.loc_zone, grp), PyImp.PixelType.GrayScale8)
            opticalResult = opticalModel.ComputeDetailedResult( origImg ) # 'n' frame of 'l' costs
            #opticalResult = opticalModel.ComputeDetailedResult(segment.GetImage())

            #print "RNN"
            txt, cost = getBestRNNOut(opticalResult, mylabels)
            #print "\t", txt, "\n\t", cost

            if not trans_model is None:
               lineFramesPredictions, rnnPredictionsWeightedByPriors = opticalResult.GetFramewiseProbasBeforePriors(), opticalResult.GetFramewiseCosts()

               # Kaldi needs "-NLL"...
               rnnPredictionsWeightedByPriors = [ map(lambda x:-x,l) for l in rnnPredictionsWeightedByPriors ]
               #-- decoding
               res = PyKaldi.decode_faster(trans_model=trans_model,
                                    decode_fst=decode_fst,
                                    rnnPredictions=rnnPredictionsWeightedByPriors,
                                    acoustic_scale=asc,
                                    decoder_opts=decoder_opts)
               end_state_reached, alignment, words, kaldiNLL, likePerFrame = res

               #lab = opticalModel.GetLabels()
               #alg = [lab.GetLabelList()[trans_model.TransitionIdToPhone(k)-1].GetId() for k in alignment]
               #txt = getBestRNNOutLM(alg)
               txt = u" ".join([output_container.GetElementFromId(wordIndex).GetWordStr() for wordIndex in words])

               #print "LM"
               cost = likePerFrame/8.0 # ??????
            txt = txt.replace(u'<s> ', '').replace(' </s>', '').replace('<space>', ' ') # dirrrrty
            txt = re.sub(ur'\s+', ' ', txt)
            print "\t", txt, "\n\t", cost
         except:
            print "Unexpected error:", sys.exc_info()[0]
            cost = 10000.

         print "minLenght",  minLenght, " cost", cost, "mincost:", minCost,
         xnc = int(max(1,floor(float((right-left)*avgCharPerPixels))))
         if len(txt) > minLenght and cost < minCost: # and abs(xnc - len(txt)) < 12:
            print " PASSOU!"
            hyplines.append(txt)
            newSegmentation.append(segment.loc_zone)
         print
   return hyplines, newSegmentation

def findLines(geo):
   detectLinesInGray = False
   # TODO: Right now, binary image is needed by CLD.
   # detect line candidates, PARAREC wants binary it seems
   if not detectLinesInGray:
      if geo.GetImage().GetPixelType() == PyImp.PixelType.GrayScale8:
         geoBinaryParagraphImageDeskewed = PyImp.ConvertGeometry(geo, PyImp.PixelType.Binary)
         PyImp.OtsuBinarization(geo.GetImage(), geoBinaryParagraphImageDeskewed.GetImage())
      else:
         geoBinaryParagraphImageDeskewed = geo
      paragraphImageDeskewed = PyHLC.GeoRefImage_ToUtilsImg(grp, geoBinaryParagraphImageDeskewed)
   else:
      # Process line segmentation on gray images.
      # Needed for example with RNN line segmentation
      if geo.GetImage().GetPixelType() == PyImp.PixelType.GrayScale8:
         geoGrayParagraphImageDeskewed = geo
      else:
         # Binary to gray conversion
         geoGrayParagraphImageDeskewed = PyImp.Convert(geo, PyImp.PixelType.GrayScale8)
      paragraphImageDeskewed = PyHLC.GeoRefImage_ToUtilsImg(grp, geoGrayParagraphImageDeskewed)

   # Apply preprocs here ?
   # store the corrected bounding box in segmentation[k].loc_zone, CRE pas content...
   # but it was just easier than having to carry on the info on the boxes
   # and have to modify the code to retrieve it from elsewhere
   para = Element('Paragraph', {'UserId':'0',})
   Top = Left = 10000000000
   Bottom = Right = -1
   nl = 0
   try:
      segmentation = detect.Process(grp, paragraphImageDeskewed)
      for k,segment in enumerate(segmentation):
         geoSegmentImg = PyHLC.GeoRefImage_FromUtilsImg(segment.extr_img)
         bb = geoSegmentImg.GetOriginalBoundingBox()
         segmentation[k].loc_zone.top = bb.top
         segmentation[k].loc_zone.left = bb.left
         segmentation[k].loc_zone.bottom = bb.bottom
         segmentation[k].loc_zone.right = bb.right
         h = bb.bottom - bb.top
         w = bb.right - bb.left
         if h >= minH and w >= minW:
            Top = min(Top, bb.top)
            Left = min(Left, bb.left)
            Right = max(Right, bb.right)
            Bottom = max(Bottom, bb.bottom)
            lin = SubElement(para, 'Line', {'Top':str(bb.top), 'Left':str(bb.left), 'Bottom':str(bb.bottom), 'Right':str(bb.right), 'Value':''})
            nl += 1
      para.set('Top', str(Top))
      para.set('Left', str(Left))
      para.set('Right', str(Right))
      para.set('Bottom', str(Bottom))
      #print "detected ", len(segmentation), " lines with pararec"
   except:
      print "Unexpected error finding lines:", sys.exc_info()[0]
   idx = 1

   grp.Reset()
   return para, nl


if __name__ == "__main__":

   from optparse import OptionParser
   parser = OptionParser(usage = """
   ======
   !!!Do not scale to very large xml files!!!

   %prog --DLparagraphs=<fileName.xml> --DLlines=<fileName.xml> --LineDetect=<string> [--RNNpath=<path>]

--DLparagraphs is the DL file from the tool that parses wikisource pages
--DLlines is the DL file with automatic line-detection and alignment of text
--RNNpath is the path to the RNN files, not it can have a different charset than the book to be recognized, but has to be more or less similar
      """)

   parser.add_option("--DLparagraphs", dest="DLparagraphs", default=None, help="Input paragraph-based DL")
   parser.add_option("--DLlines", dest="DLlines", default=None, help="Output line-based DL")
   parser.add_option("--RNNpath", dest="RNNpath", default=None, help="Path to RNN files")
   parser.add_option("--LMpath", dest="LMpath", default=None, help="Path to character n-gram")
   parser.add_option("--LineDetect", dest="LineDetect", default="CLD", help="Algo for line detection")
   parser.add_option('--minW', help='minimum line width (px) for acceptance', dest = 'minW', default = '7')
   parser.add_option('--minH', help='minimum line height (px) for acceptance', dest = 'minH', default = '7')
   parser.add_option('--minLenght', help='minimum line length (chars) for acceptance', dest = 'minLenght', default = '1')
   parser.add_option('--minCost', help='minimum cost (for a RNN line) for acceptance', dest = 'minCost', default = '1.01')
   parser.add_option('--minDist', help='minimum distance between words (cost) for acceptance', dest = 'minDist', default = '2.0')
   parser.add_option('--minCER', help='minimum CER (errors) for acceptance', dest = 'minCER', default = '30.0')
   parser.add_option('--deskew', help='Apply deskew to the paragraph images', dest = 'deskew', default=False)
   parser.add_option("--Newpath", dest="Newpath", default=None, help="Prefix path to store line images")
   (options, args) = parser.parse_args()

   ############################################################
   # "HARDCODED" parameters go here, they are not in the usage so they remain "hidden" for most eyes
   minW = int(options.minW) # px
   minH = int(options.minH) # px
   minLenght = int(options.minLenght) # in chars
   minCost = float(options.minCost)
   minDist = float(options.minDist)
   minCER = float(options.minCER)
   #
   # rnn Setup
   #
   asc = 2.0 # acoustic weight
   ps = 0.7 # a priori scale

   applyDeskew = options.deskew

   # boilerplate stuff ##########################################
   if options.DLparagraphs is not None:
      options.DLparagraphs = os.path.expanduser(options.DLparagraphs)
      if not os.path.isfile(options.DLparagraphs):
         raise RuntimeError, "ERROR: Input DL list <%s> does not exist!\n"%options.DLparagraphs
   else:
      raise RuntimeError, "ERROR: You should give a paragraph-based DL file! --DLparagraphs"

   if options.DLlines is not None:
      options.DLlines = os.path.expanduser(options.DLlines)
   else:
      raise RuntimeError, "ERROR: You should give a name for output line-based DL file! --DLlines"

   #if options.RNNpath is not None:
      #options.RNNpath = os.path.expanduser(options.RNNpath)
      #if not os.path.isdir(options.RNNpath):
         #raise RuntimeError, "ERROR: Path for RNN files <%s> does not exist!\n"%options.RNNpath
   #else:
      #raise RuntimeError, "ERROR: You should give a path for RNN files --RNNpath !"
   #LMpath = None
   #if options.LMpath is not None:
      #LMpath = os.path.expanduser(options.LMpath)
      #if not os.path.isdir(LMpath):
         #raise RuntimeError, "ERROR: Path for language model files <%s> does not exist!\n"%LMpath

   #if not options.Newpath is None:
      #deskewPath = os.path.expanduser(options.Newpath)
   #else:
      #raise RuntimeError, "ERROR: You should give a path prefix for line images: --Newpath!"


   ######################################################################
   #opticalModel = PyNN.NN3_OpticalModel(options.RNNpath, priorsStrategy=PyNN.PriorsStrategy_ScaledPriors(priorsScale=asc))
   #opticalModel.Static()

   #charset= opticalModel.GetLabels()
   #utf8stringSplitter = PyNN.NN3_AnnotationSplitter_Utf8SymbolDefaultImpl(False)
   #utf8stringSplitter.Init(charset)

   #blankS= None
   #useBlank = False
   #for i, label in enumerate( charset ):
      #if label.GetId()==PyNN.NN3_Label.GetReservedBlankId():
         #assert blankS is None
         #blankS = PyNN.NN3_Label.GetReservedBlankId()
         #useBlank = True

   #outputs = decode_fst = trans_model = decoder_opts = None
   #if not LMpath is None:
      #vocPath = os.path.join(LMpath,"words.txt")
      #if not os.path.exists(vocPath):
         #raise RuntimeError("'%s' does not exist" % vocPath)
      #outputs = TRC.ReadKaldiLabelFile(vocPath)
      #output_container, wordIndexTransformer, spaceCharIndices = CreateContainerFromWords(outputs)

      ##-- load the decoding graph
      #HCLGFstPath = os.path.join(LMpath ,"HCLG.fst")
      #if not os.path.exists(HCLGFstPath) and not os.path.exists(HCLGFstPath+".zip"):
         #raise RuntimeError("'%s' does not exist" % HCLGFstPath)
      #decode_fst = TRC.LoadStdVectorFst(os.path.dirname(HCLGFstPath), "HCLG.fst")

      ##-- create necessary objects for decoding
      #hmmModelPath = os.path.join(LMpath,"hmm.mdl")
      #if not os.path.exists(hmmModelPath):
         #raise RuntimeError("'%s' does not exist" % hmmModelPath)
      #trans_model = PyKaldi.TransitionModel()
      #PyKaldi.ReadKaldiObject(hmmModelPath, trans_model)

      #decoder_opts = PyKaldi.FasterDecoderOptions()
      #decoder_opts.beam = 20

   #mylabels = [k.GetId() for k in opticalModel.GetLabels().GetLabelList()]
   #charsInRNN = [unicode(k.GetId(), 'utf-8') for k in opticalModel.GetLabels().GetLabelList()]
   #charsInRNN.remove(blankS)

   paragraphRect = PyCore.UtilsRect()

   # line detector
   #########################################################
   detect = TLD.CreateTextLineDetector(PyX.UtilsCountry.FR, PyX.Utils_Write_Handwr, options.LineDetect)


   # the FUN begins here!
   dlist = open(options.DLlines, 'w')
   dlist.write('<?xml version="1.0" encoding="utf-8"?>' + '\n') # Dirty tweak: XML declaration by hand:
   dlist.write('<DocumentList>\n')

   # process the paragraph-level annotated xml, ignore pages without Value for Paragraph
   grp = PyCore.AllocGrp()

   totLin = 0
   totPL = 0
   for _,page in et.iterparse(options.DLparagraphs) :
      if page.tag == "SinglePage" :
         srcPageImage = page.get("FileName")
         filenameAbsPath = PyCore.GetFileTabKob().ToAbsolute(srcPageImage, True)
         part_lin = part_PL = 0
         newPage = Element('SinglePage', {"FileName":srcPageImage})
         if not os.path.exists(filenameAbsPath):
            print "WARNING: Could not find image file " + filenameAbsPath
         else:
            print "Processing", filenameAbsPath
            img = PyImageIO.GeoRefImageLoader().SetInput(filenameAbsPath).Load()
            geo2 = img
            # make the image grayscale if not already GS or B&W
            if img.GetImage().GetPixelType() != PyImp.PixelType.GrayScale8 and img.GetImage().GetPixelType() != PyImp.PixelType.Binary:
               geo2=PyImp.ConvertGeometry(img, PyImp.PixelType.GrayScale8)
               PyImp.RGBToLuminance(img.GetImage(), geo2.GetImage())
            if geo2.GetImagePixelType() == PyImp.PixelType.GrayScale8:
               #uimg = PyHLC.GeoRefImage_FromUtilsImg(geo2, PyImp.PixelType.GrayScale8)
               whitePixel = PyImp.CreatePixelValueFromInt(PyImp.PixelType.GrayScale8, 255)
            elif geo2.GetImagePixelType() == PyImp.PixelType.Binary:
               #uimg = PyHLC.GeoRefImage_FromUtilsImg(geo2, PyImp.PixelType.Binary)
               whitePixel = PyImp.CreatePixelValueFromInt(PyImp.PixelType.Binary, 0)
            else:
               raise RuntimeError("Image is not Binary nor grayscale => unsupported.")

            gotLines = False
            parai = 0

            for parai, snippet in enumerate(page.getiterator('Paragraph')):
               print "\tParagraph", parai
               paragraphRect.left   = int(snippet.get("Left"))
               paragraphRect.right  = int(snippet.get("Right"))
               paragraphRect.top    = int(snippet.get("Top"))
               paragraphRect.bottom = int(snippet.get("Bottom"))

               # Ensure that the rect is well included in the image and is non-null.
               if paragraphRect.left < 0:
                  paragraphRect.left = 0
               if paragraphRect.top < 0:
                  paragraphRect.top = 0
               if paragraphRect.right > img.GetImage().GetXSize():
                  paragraphRect.right = img.GetImage().GetXSize()
               if paragraphRect.bottom > img.GetImage().GetYSize():
                  paragraphRect.bottom = img.GetImage().GetYSize()
               if paragraphRect.bottom <= paragraphRect.top:
                  raise RuntimeError("bottom = " + str(paragraphRect.bottom) + " and top = " + str(paragraphRect.top))
               # paranoid
               if paragraphRect.right > paragraphRect.left and paragraphRect.bottom > paragraphRect.top:
                  poly = snippet.get('Polygon')
                  if not poly is None:
                     polygon = [(int(p.split(',')[0]), int(p.split(',')[1])) for p in poly.split()]
                     polygon = [PyImp.Point(p[0], p[1]) for p in polygon]
                  else:
                     polygon = [PyImp.Point(paragraphRect.left, paragraphRect.top),
                              PyImp.Point(paragraphRect.left, paragraphRect.bottom),
                              PyImp.Point(paragraphRect.right, paragraphRect.bottom),
                              PyImp.Point(paragraphRect.right, paragraphRect.top)]
                  gpara = PyImp.GetSubImageFromPolygonWithClipping(geo2, polygon, whitePixel)
                  paraDeskew = gpara
                  if applyDeskew:
                     paraDeskew = PyImp.BloombergSkewCorrectionAsNewGeoRef(gpara, -1.0, 1.0, whitePixel)
                     # we store the de-skew images, also in the output DL, but for each detected line
                  para, nfl = findLines(gpara)
                  if nfl > 0:
                     newPage.append(para)
                     part_PL += 1
                  part_lin += nfl
               else:
                  print ">>>ERROR: bad paragraph crop: (t,l,r,b) = ",paragraphRect.top, paragraphRect.left, paragraphRect.right, paragraphRect.bottom
            totPL += part_PL
            totLin += part_lin
            if part_PL > 0:
               indent(newPage)
               print >> dlist, ET.tostring(newPage,encoding="utf-8")
            print "Identified", part_lin, "lines out of", part_PL
            #if totPL > 5: break

   print "Identified", totLin, "lines out of", totPL
   dlist.write('</DocumentList>\n')
   dlist.close()
