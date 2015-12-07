# -*- coding: utf-8 -*-

##
# @author RM
# @brief  Get a pdf file, convert it to tif images, then de-skew and recognize lines with a given RNN&LM, the result is a DL xml file
# @date   July 2015

import sys, os
import string, re
import unicodedata
import fnmatch
from random import randrange
import shutil, tempfile
import itertools

# stop bothering us with ascii crap
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


if __name__ == "__main__":

   from optparse import OptionParser
   parser = OptionParser(usage = """
   ======

 
   %prog --PDF=<fileName.pdf> --imagePath=<Path> --pagePrefix=<string> [--resol=<integer, default=300]
      """)

   #parser.add_option("--gutenberg", dest="gutenberg", default=None, help="text file from Gutenberg project, stripped of useless book info")
   parser.add_option("--PDF", dest="PDF", default=None, help="Input PDF file")   
   parser.add_option("--imagePath", dest="imagePath", default=None, help="Path to store page files")
   parser.add_option('--pagePrefix', help='Prefix for each page', dest = 'pagePrefix', default = None)
   parser.add_option('--resol', help='Resolution (dpi) of output images', dest = 'resol', default = 300)

   #parser.add_option('-s', help='Split numeric strings into digits', dest = 'splitDigits', action="store_true")
   (options, args) = parser.parse_args()

   ############################################################
   # boilerplate stuff 
   if not options.PDF is None:
      options.PDF = os.path.expanduser(options.PDF)
      #print "<%s>"%options.PDF
      if not os.path.isfile(options.PDF):
         raise RuntimeError, "ERROR: Input PDF file <%s> does not exist!\n"%options.PDF
   else:
      raise RuntimeError, "ERROR: You should give a PDF file! --PDF"
   
   if not options.pagePrefix:
      raise RuntimeError, "ERROR: You should give a prefix for output files! --pagePrefix"

   if not options.imagePath is None:
      options.imagePath = os.path.expanduser(options.imagePath)
      if not os.path.isdir(options.imagePath):
         print ">>>Making %s"%options.imagePath
         os.makedirs(options.imagePath)
         #raise RuntimeError, "ERROR: Path for outout tif files <%s> does not exist!\n"%options.imagePath
   else:
      raise RuntimeError, "ERROR: You should give a path for output TIF files --imagePath !"
   

   options.PDF = options.PDF.replace(' ', '\\ ')
   #print "<%s>"%options.PDF

   # first convert the pdf into a bunch of temporary tif files at the given resolution
   import subprocess
   cmd = 'gs -r'+str(options.resol)+'x'+str(options.resol)+' -o '+ os.path.join(options.imagePath, options.pagePrefix + '_%04d.tif') + ' -sDEVICE=tiffgray ' +  options.PDF
   #print "cmd <%s>"%cmd
   try:
      ret = subprocess.check_output(cmd, shell=True)
   except:
      raise RuntimeError, ">>>ERROR: Could not convert the pdf file with gs...\n", cmd
   #pos = ret.rfind('Page ')

