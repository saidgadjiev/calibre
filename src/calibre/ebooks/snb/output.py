# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import os, string

from lxml import etree
from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre.ptempfile import TemporaryDirectory
from calibre.constants import __appname__, __version__
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.snb.snbfile import SNBFile
from calibre.ebooks.snb.snbml import SNBMLizer

def ProcessFileName(fileName):
    # Flat the path 
    fileName = fileName.replace("/", "_").replace(os.sep, "_")
    # Handle bookmark for HTML file
    fileName = fileName.replace("#", "_")
    # Make it lower case
    fileName = fileName.lower()
    # Change extension for image files to png
    root, ext = os.path.splitext(fileName) 
    if ext in [ '.jpeg', '.jpg', '.gif', '.svg' ]:
        fileName = root + '.png'
    return fileName
    

class SNBOutput(OutputFormatPlugin):

    name = 'SNB Output'
    author = 'Li Fanxi'
    file_type = 'snb'

    options = set([
        # OptionRecommendation(name='newline', recommended_value='system',
        #     level=OptionRecommendation.LOW,
        #     short_switch='n', choices=TxtNewlines.NEWLINE_TYPES.keys(),
        #     help=_('Type of newline to use. Options are %s. Default is \'system\'. '
        #         'Use \'old_mac\' for compatibility with Mac OS 9 and earlier. '
        #         'For Mac OS X use \'unix\'. \'system\' will default to the newline '
        #         'type used by this OS.') % sorted(TxtNewlines.NEWLINE_TYPES.keys())),
        OptionRecommendation(name='output_encoding', recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. ' \
            'The default is utf-8. Note: This option is not honored by all ' \
            'formats.')),
        # OptionRecommendation(name='inline_toc',
        #     recommended_value=False, level=OptionRecommendation.LOW,
        #     help=_('Add Table of Contents to beginning of the book.')),
        OptionRecommendation(name='max_line_length',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The maximum number of characters per line. This splits on '
            'the first space before the specified value. If no space is found '
            'the line will be broken at the space after and will exceed the '
            'specified value. Also, there is a minimum of 25 characters. '
            'Use 0 to disable line splitting.')),
        # OptionRecommendation(name='force_max_line_length',
        #     recommended_value=False, level=OptionRecommendation.LOW,
        #     help=_('Force splitting on the max-line-length value when no space '
        #     'is present. Also allows max-line-length to be below the minimum')),
     ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        # Create temp dir
        with TemporaryDirectory('_snb_output') as tdir:
            # Create stub directories
            snbfDir = os.path.join(tdir, 'snbf') 
            snbcDir = os.path.join(tdir, 'snbc')
            snbiDir = os.path.join(tdir, 'snbc/images')
            os.mkdir(snbfDir)
            os.mkdir(snbcDir)
            os.mkdir(snbiDir)

            # Process Meta data
            meta = oeb_book.metadata
            if meta.title:
                title = unicode(meta.title[0])
            else:
                title = ''
            authors = [unicode(x) for x in meta.creator if x.role == 'aut']
            if meta.publisher:
                publishers = unicode(meta.publisher[0])
            else:
                publishers = ''
            if meta.language:
                lang = unicode(meta.language[0]).upper()
            else:
                lang = ''
            if meta.description:
                abstract = unicode(meta.description[0])
            else:
                abstract = ''

            # Process Cover
            from calibre.ebooks.oeb.base import urldefrag
            g, m, s = oeb_book.guide, oeb_book.manifest, oeb_book.spine
            href = None
            if 'titlepage' not in g:
                if 'cover' in g:
                    href = g['cover'].href

            # Output book info file
            bookInfoTree = etree.Element("book-snbf", version="1.0")
            headTree = etree.SubElement(bookInfoTree, "head")
            etree.SubElement(headTree, "name").text = title
            etree.SubElement(headTree, "author").text = ' '.join(authors)
            etree.SubElement(headTree, "language").text = lang
            etree.SubElement(headTree, "rights")
            etree.SubElement(headTree, "publisher").text = publishers
            etree.SubElement(headTree, "generator").text = __appname__ + ' ' + __version__
            etree.SubElement(headTree, "created")
            etree.SubElement(headTree, "abstract").text = abstract
            if href != None:
                etree.SubElement(headTree, "cover").text = ProcessFileName(href)
            else:
                etree.SubElement(headTree, "cover")
            bookInfoFile = open(os.path.join(snbfDir, 'book.snbf'), 'wb')
            bookInfoFile.write(etree.tostring(bookInfoTree, pretty_print=True, encoding='utf-8'))
            bookInfoFile.close()
            
            # Output TOC
            tocInfoTree = etree.Element("toc-snbf")
            tocHead = etree.SubElement(tocInfoTree, "head")
            tocBody = etree.SubElement(tocInfoTree, "body")
            outputFiles = { }
            if oeb_book.toc.count() == 0:
                log.warn('This SNB file has no Table of Contents. '
                    'Creating a default TOC')
                first = iter(oeb_book.spine).next()
                oeb_book.toc.add(_('Start'), first.href)

            for tocitem in oeb_book.toc:
                if tocitem.href.find('#') != -1:
                    item = string.split(tocitem.href, '#')
                    if len(item) != 2:
                        log.error('Error in TOC item: %s' % tocitem)
                    else:
                        if item[0] in outputFiles:
                            outputFiles[item[0]].append((item[1], tocitem.title)) 
                        else:
                            outputFiles[item[0]] = [] 
                            if not "" in outputFiles[item[0]]:
                                outputFiles[item[0]].append(("", _("Start"))) 
                                ch = etree.SubElement(tocBody, "chapter")
                                ch.set("src", ProcessFileName(item[0]) + ".snbc")
                                ch.text = _("Start")
                            outputFiles[item[0]].append((item[1], tocitem.title)) 
                else:
                    if tocitem.href in outputFiles:
                        outputFiles[tocitem.href].append(("", tocitem.title)) 
                    else:
                        outputFiles[tocitem.href] = [] 
                        outputFiles[tocitem.href].append(("", tocitem.title))
                ch = etree.SubElement(tocBody, "chapter")
                ch.set("src", ProcessFileName(tocitem.href) + ".snbc")
                ch.text = tocitem.title


            etree.SubElement(tocHead, "chapters").text = '%d' % len(tocBody)

            tocInfoFile = open(os.path.join(snbfDir, 'toc.snbf'), 'wb')
            tocInfoFile.write(etree.tostring(tocInfoTree, pretty_print=True, encoding='utf-8'))
            tocInfoFile.close()

            # Output Files
            for item in s:
                from calibre.ebooks.oeb.base import OEB_DOCS, OEB_IMAGES, PNG_MIME
                if m.hrefs[item.href].media_type in OEB_DOCS:
                    if not item.href in outputFiles:
                        log.debug('Skipping %s because unused in TOC.' % item.href)
                        continue
                    log.debug('Converting %s to snbc...' % item.href)
                    snbwriter = SNBMLizer(log)
                    snbcTrees = snbwriter.extract_content(oeb_book, item, outputFiles[item.href], opts)
                    for subName in snbcTrees:
                        postfix = ''
                        if subName != '':
                             postfix = '_' + subName
                        outputFile = open(os.path.join(snbcDir, ProcessFileName(item.href + postfix + ".snbc")), 'wb')
                        outputFile.write(etree.tostring(snbcTrees[subName], pretty_print=True, encoding='utf-8'))
                        outputFile.close()
            for item in m:
                if m.hrefs[item.href].media_type in OEB_IMAGES:
                    log.debug('Converting image: %s ...' % item.href)
                    content = m.hrefs[item.href].data
                    if m.hrefs[item.href].media_type != PNG_MIME:
                        # Convert & Resize image
                        self.HandleImage(content, os.path.join(snbiDir, ProcessFileName(item.href)))
                    else:
                        outputFile = open(os.path.join(snbiDir, ProcessFileName(item.href)), 'wb')
                        outputFile.write(content)
                        outputFile.close()
            
            # Package as SNB File
            snbFile = SNBFile()
            snbFile.FromDir(tdir)
            snbFile.Output(output_path)

    def HandleImage(self, imageData, imagePath):
        from calibre.utils.magick import Image
        img = Image()
        img.load(imageData)
        (x,y) = img.size
        # TODO use the data from device profile
        SCREEN_X = 540
        SCREEN_Y = 700
        # Handle big image only
        if x > SCREEN_X or y > SCREEN_Y:
            SCREEN_RATIO = float(SCREEN_Y) / SCREEN_X
            imgRatio = float(y) / x
            xScale = float(x) / SCREEN_X
            yScale = float(y) / SCREEN_Y
            scale = max(xScale, yScale)
            # TODO : intelligent image rotation
            #     img = img.rotate(90)
            #     x,y = y,x
            img.size = (x / scale, y / scale)
        img.save(imagePath)

if __name__ == '__main__':
    from calibre.ebooks.oeb.reader import OEBReader
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
    from calibre.customize.profiles import HanlinV3Output
    class OptionValues(object):
        pass

    opts = OptionValues()
    opts.output_profile = HanlinV3Output(None)
    
    html_preprocessor = HTMLPreProcessor(None, None, opts)
    from calibre.utils.logging import default_log
    oeb = OEBBook(default_log, html_preprocessor)
    reader = OEBReader
    reader()(oeb, '/tmp/bbb/processed/')
    SNBOutput(None).convert(oeb, '/tmp/test.snb', None, None, default_log);
