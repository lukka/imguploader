#!/usr/bin/env python

''' imguploader: a script to upload files to online image hosting services, and
    to create an HTML file with links to those images.
'''

import configparser
import sys
from PIL import Image
from PIL import ExifTags
import os
import re
import logging
from argparse import ArgumentParser
from importlib import import_module
import fcntl
import traceback

''' The default logging level is set to  logging.INFO'''
CONSOLE_DEFAULT_LEVEL = logging.INFO

''' Convert the string of the logging level to a integer
    Fallback to CONSOLE_DEFAULT_LEVEL if the string is not a valid integer '''
def getConsoleLevel(levelString):
    try:
        level = int(levelString)
    except:
        level = CONSOLE_DEFAULT_LEVEL
    return level

''' UploadedImage represents an image uploaded to the hosting service: it stores the local file name
    of the image, the URL to the full image, and the URL of the thumb image uploaded on the hosting service.
    Note that in principle an entry is not tied to any specific hosting service nor to a specific backend class.
'''
class UploadedImage():

    def __init__(self, pFileName, pURLFullImage, pURLThumbImage):
        self._fileName = pFileName
        self._URLFullImage = pURLFullImage
        self._URLThumbImage = pURLThumbImage

    def getImageFileName(self):
        return self._fileName

    def getURLFullImage(self):
        return self._URLFullImage

    def getURLThumbImage(self):
        return self._URLThumbImage
    
    def __str__(self):
        return ("[UploadedImage _fileName='%s' _URLFullImage='%s' _URLThumbImage='%s']") % (self._fileName, self._URLFullImage, self._URLThumbImage);

''' Minimalist exception class for exception casted by the UploadedImagesTracker class.'''
class UploadedImagesTrackerException(Exception):
    pass

''' Failure when trying to acquire the lock file '''
class UploadedImagesTrackerLockAcquiringFailed(Exception):
    pass


''' Class UploadedImagesTracker main duties:
    -Keeps track of uploaded image in an 'activity log file'; this is mostly done in order to restart the uploading after
     an interruption, saving the time and bandwidth used by the already uploaded images.
    -Grants exclusive access to the same file.

    This class should be used by using the 'with UploadedImagesTracker() as xxx' pattern.
'''
class UploadedImagesTracker():

    ''' Separator character between fields of the activity log file. '''
    _ACTIVITYLOG_TOKEN_SEPARATOR = "<"
    ''' Activity log file name. '''
    _ACTIVITYLOG_FILE_NAME = '.imguploader_activity_log_file'

    def __init__(self, pDirectory):
        self._uploadedImages = []
        self._activityLogFile = open(os.path.join(pDirectory, self._ACTIVITYLOG_FILE_NAME), 'a+')
        self._activityLogFile.seek(0, os.SEEK_SET) #Move to the beginning of the file.
        ''' Try to execute a non blocking lock on the activity log file.
            If another instance of this script is already running in the same
            directory, then the activity log is already locked and the script would exit. '''
        try:
            fcntl.flock(self._activityLogFile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise UploadedImagesTrackerLockAcquiringFailed("Activity log file ({0}) cannot be locked.".format(self._ACTIVITYLOG_FILE_NAME))

        '''
        Recreate (from the activity log file) the list of already uploaded files, storing them into self._uploadedImages.
        '''
        content = self._activityLogFile.readlines()
        for textLine in content:
            textLineTokenized = textLine.strip().split(self._ACTIVITYLOG_TOKEN_SEPARATOR)
            if(len(textLineTokenized) != 3):
                raise UploadedImagesTrackerException("Activity log file corrupted ({0}), remove it.".format(self._ACTIVITYLOG_FILE_NAME))
            self._uploadedImages.append(UploadedImage(textLineTokenized[0], textLineTokenized[1],
                textLineTokenized[2]))

    def __enter__(self):
        return self

    def __exit__(self, pType, pValue, pTraceback):
        self._activityLogFile.close()

    ''' @return Whether the image file has already been uploaded. This is determined by inspecting the activity log file.
    '''
    def isImageAlreadyUploaded(self, imageFileName):
        found = [i for i, triple in enumerate(self._uploadedImages) if triple.getImageFileName() == imageFileName]
        return found != []

    '''
    Add an already uploaded image to the activity log file.
    @param fileName The filename (not including the path) of the image that has been already uploaded.
    '''
    def addUploadedImage(self, fileName, URLFullImage, URLThumbImage):
        '''Move file pointer to the end of file.'''
        self._activityLogFile.seek(0, 2)

        uploadedImage = UploadedImage(fileName, URLFullImage, URLThumbImage)
        self._activityLogFile.write(uploadedImage.getImageFileName()+self._ACTIVITYLOG_TOKEN_SEPARATOR+
            uploadedImage.getURLFullImage()+self._ACTIVITYLOG_TOKEN_SEPARATOR+
            uploadedImage.getURLThumbImage()+"\n")
        ''' Store an entry in the _uploadedImages list that denotes that this image has been successfully uploaded. '''
        self._uploadedImages.append(uploadedImage)

    def getImageList(self):
        return self._uploadedImages


''' Minimalist exception class for the exceptions casted by the ImageUploader class.'''
class ImageUploaderException(Exception):
    pass




'''
    Main tasks:
    -parse and validate the configuration file;
    -upload images by means of a backend; 
    -implement the upload policy: every successfully uploaded file is noted in an activity log file; whenever a file
     to be uploaded is already noted as uploaded in the activity log file, this file is skipped and it is not uploaded.
    -generate in a file the HTML content to copy and paste into a eBay listing;
'''
class ImageUploader:

    '''
        Given a configuration parser object, and a section name, it creates the 
        corresponding dictionary with key-value pairs.
        @param configuration The ConfigParser object
        @param sectionString The name of the string to look at inside the configuration parser object.
    '''
    def _configParserSectionToDict(self, configuration, sectionString):
        dictOfTheSection = {}
        options = configuration.options(sectionString)
        for option in options:
            try:
                dictOfTheSection[option] = configuration.get(sectionString, option)
                if dictOfTheSection[option] == -1:
                    self._getLog().warning("skip: %s" % option)
            except:
                self._getLog().error("exception on %s!" % option)
                dictOfTheSection[option] = None
        return dictOfTheSection

    ''' Class variables '''
    _CFG_CONFIG_FILE_NAME = '.imguploader.cfg'
    _CFG_CONFIG_SECTION_NAME = "config"
    _CFG_TMP_DIRECTORY_PATH = "tmpDirPath"
    _CFG_OUTPUT_HTML_FILENAME = "outputHTMLFilename"
    _CFG_TARGET_IMAGE_WIDTH = "targetImageWidthPx"
    _CFG_TARGET_IMAGE_HEIGHT = "targetImageHeightPx"
    _CFG_THUMB_IMAGE_WIDTH = "thumbImageWidthPx"
    _CFG_THUMB_IMAGE_HEIGHT = "thumbImageHeightPx"
    _CFG_HTML_HEADER_FILE_PATH = "HTMLHeaderFilePath"
    _CFG_HTML_FOOTER_FILE_PATH = "HTMLFooterFilePath"
    _CFG_OAUTH_CLIENT_ID = "oauthClientId"
    _CFG_OAUTH_SECRET = "oauthSecret"
    _CFG_BACKEND_CLASS = "hostingServerBackendClass"

    ''' Initialize the instance by reading settings from the configuration file
        and using fallback values when the configuration file is not available or incomplete'''
    def __init__(self, srcImgDir, logLevel = CONSOLE_DEFAULT_LEVEL,):
        self._sourceImageDirectory = srcImgDir
        self._targetImageSize = (1280, 1280)
        self._thumbImageSize = (320, 320)
        ''' _htmlHeaderFilePath is either set to None (since it is optional), either set to an existent path.'''
        self._htmlHeaderFilePath = None
        ''' _htmlFooterFilePath is either set to None (as it is optional), either set to an existent path.'''
        self._htmlFooterFilePath = None
        self._tmpDirectory = None
        self._outputHTMLFilename = None
        self._oauthClientId = None
        self._oauthSecret = None
        self._backendClass = None

        self._loggingInit(logLevel)
        ''' Read, parse and validate the configuration file '''
        self._parseValidateConfigurationFile()

    ''' Get a value from the dictionary aDict whose key is keyName
        If the key is not found 'defaultValue' is returned instead '''
    def _getOptionalValue(self, aDict, keyName, defaultValue):
        ret = defaultValue
        if keyName in aDict:
            ret = aDict[keyName]
        return ret

    ''' Get a value from the dictionary aDict whose key is keyName
        if the key is not found, None is returned
    '''
    def _getRequiredValue(self, aDict, keyName):
        ret = None
        if keyName in aDict:
            ret = aDict[keyName]
        return ret

    ''' Convert aString to an integer. Return a tuple as in ('conversion success, either True or False', 'integer value')
    '''
    def _convertToInt(self, aString):
        try:
            i = int(aString)
            return (True, i)
        except Exception:
            return (False, 0)

    ''' Convert aString to an integer and raise an ImageUploaderException exception
        whenever the conversion fails '''
    def _raiseErrorWhetherNotAnInt(self, aString, optionName):
        ret = self._convertToInt(aString)
        if not ret[0]:
            raise ImageUploaderException("The provided value \"{1}\" for option \"{0}\" is not a valid integer".format(optionName, aString))
        else:
            return ret[1]

    ''' Validate a file name: only alphanumeric characters and  "_", "." and "-" are allowed. '''
    def _validateFileName(self, aFileName):
        return not re.search(r'[^A-Za-z0-9\._\-]', aFileName)

    ''' Validate a path (either a file or a directory path), verifying whether:
        - the path is existent;
        - the path is accessible with permission described in 'access'.
    '''
    def _validatePath(self, aPath, access):
        if not os.path.exists(aPath):
            return False
        if not os.access(os.path.dirname(aPath), access):
            return False
        return True

    ''' Raise an exception of type ImageUploaderException containing in the description the missing setting
        name provided in 'settingName' '''
    def _raiseMissingSetting(self, settingName):
        raise ImageUploaderException("\"{0}\" is missing in the configuration file.".format(settingName))

    ''' Return True when the provided 'OAuthString' is a string, False otherwise. '''
    def _validateOAuthString(self, OAuthString):
        return isinstance(OAuthString, str) or len(OAuthString)

    ''' @brief Load a configuration file: either in the $HOME directory, or in the
        current working directory.
        @remark Throws ImageUploaderException when no config file has been loaded.
    '''
    def _loadConfigurationFile(self, pConfigParser):
        userConfigFilePath = os.path.expanduser(os.path.join("~", ImageUploader._CFG_CONFIG_FILE_NAME))
        localConfigFilePath = os.path.join(".", ImageUploader._CFG_CONFIG_FILE_NAME)
        foundFile = pConfigParser.read(userConfigFilePath)
        if not foundFile:
            foundFile = pConfigParser.read(localConfigFilePath)
            if not foundFile:
                raise ImageUploaderException("No config file was found, nor {0} nor {1}.".format(userConfigFilePath, localConfigFilePath))
        self._getLog().info("Loaded configurations file {0}".format(foundFile[0]))

    ''' Validate and parse the configuration file
        Raise an ImageUploaderException exception for any error encountered during the parsing of the
        configuration file. '''
    def _parseValidateConfigurationFile(self):
        self._getLog().info("Loading configuration file...")
        configParser = configparser.ConfigParser()
        configParser.optionxform=str #This force to preserve the case of the keys in the configuration file.
        self._loadConfigurationFile(configParser)
        if not configParser.has_section(ImageUploader._CFG_CONFIG_SECTION_NAME):
            raise ImageUploaderException("The configuration file(s) does not provide the required \"[config]\" section.")

        ''' Retrieve the values stored in the configuration file '''
        sectionDict = self._configParserSectionToDict(configParser, ImageUploader._CFG_CONFIG_SECTION_NAME)

        self._tmpDirectory = self._getRequiredValue(sectionDict, ImageUploader._CFG_TMP_DIRECTORY_PATH)
        if self._tmpDirectory is None:
            self._raiseMissingSetting(ImageUploader._CFG_TMP_DIRECTORY_PATH);
        if not self._validatePath(self._tmpDirectory, os.R_OK | os.W_OK):
            raise ImageUploaderException("The temporary directory \"{0}\" does not exist or it is not accessible.".format(self._tmpDirectory))

        self._outputHTMLFilename = self._getOptionalValue(sectionDict, ImageUploader._CFG_OUTPUT_HTML_FILENAME, "listing.html")
        if not self._validateFileName(self._outputHTMLFilename):
            raise ImageUploaderException("Invalid output HTML file name \"{0}\", it must contains only alphanumeric characters.".format(self._outputHTMLFilename))

        widthPx = self._getOptionalValue(sectionDict, ImageUploader._CFG_TARGET_IMAGE_WIDTH, self._targetImageSize[0])
        heightPx = self._getOptionalValue(sectionDict, ImageUploader._CFG_TARGET_IMAGE_HEIGHT, self._targetImageSize[1])
        self._targetImageSize = (self._raiseErrorWhetherNotAnInt(widthPx, ImageUploader._CFG_TARGET_IMAGE_WIDTH),
                                 self._raiseErrorWhetherNotAnInt(heightPx, ImageUploader._CFG_TARGET_IMAGE_HEIGHT))
        thumbWidthPx = self._getOptionalValue(sectionDict, ImageUploader._CFG_THUMB_IMAGE_WIDTH, self._thumbImageSize[0])
        thumbHeightPx = self._getOptionalValue(sectionDict, ImageUploader._CFG_THUMB_IMAGE_HEIGHT, self._thumbImageSize[1])
        self._thumbImageSize = (self._raiseErrorWhetherNotAnInt(thumbWidthPx, ImageUploader._CFG_THUMB_IMAGE_WIDTH),
                                 self._raiseErrorWhetherNotAnInt(thumbHeightPx, ImageUploader._CFG_THUMB_IMAGE_HEIGHT))

        self._oauthClientId = self._getRequiredValue(sectionDict, ImageUploader._CFG_OAUTH_CLIENT_ID)
        if self._oauthClientId is None:
            self._raiseMissingSetting(ImageUploader._CFG_OAUTH_CLIENT_ID)
        if not self._validateOAuthString(self._oauthClientId):
            raise ImageUploaderException("{0} is not a valid string: \"{1}\".".format(ImageUploader._CFG_OAUTH_CLIENT_ID, self._oauthClientId))

        self._oauthSecret = self._getOptionalValue(sectionDict, ImageUploader._CFG_OAUTH_SECRET, None)
        if self._oauthSecret is None:
            self._raiseMissingSetting(ImageUploader._CFG_OAUTH_SECRET)
        if not self._validateOAuthString(self._oauthSecret):
            raise ImageUploaderException("{0} is not a valid string: \"{1}\".".format(ImageUploader._CFG_OAUTH_SECRET, self._oauthClientId))

        backendClassStr = self._getRequiredValue(sectionDict, ImageUploader._CFG_BACKEND_CLASS)
        if backendClassStr is None:
            self._raiseMissingSetting(ImageUploader._CFG_BACKEND_CLASS)
        try:
            lBackendsModule = import_module("imgbackends")
            self._backendClass = getattr(lBackendsModule, backendClassStr)
        except Exception as exc:
            raise ImageUploaderException("Value \"{1}\" for {0} triggered exception: '{2}'.".format(self._CFG_BACKEND_CLASS, backendClassStr, str(exc)))
        try:
            interfaceCompletenessTest = self._backendClass()
            interfaceCompletenessTest.setSecret(None)
            interfaceCompletenessTest.setClientId(None)
            interfaceCompletenessTest.uploadImage(None)
            interfaceCompletenessTest.getDescriptiveName()
        except (AttributeError, TypeError) as ex:
            raise ImageUploaderException("The provided backend class \"{0}\" does not fully implement the interface ImageHostingServerBackendInterface ({2}).".format(self._CFG_BACKEND_CLASS, backendClassStr, str(ex)))

        self._htmlHeaderFilePath = self._getOptionalValue(sectionDict, ImageUploader._CFG_HTML_HEADER_FILE_PATH, "")

        self._htmlFooterFilePath = self._getOptionalValue(sectionDict, ImageUploader._CFG_HTML_FOOTER_FILE_PATH, "")

    def getImageSourceDirectory(self):
        return self._sourceImageDirectory

    '''When an output file already exist, do not overwrite it: in fact
        rename the already existing file appending a progressive number, like ".NNN" where
        NNN is the progressive number.'''
    def _renameExistingFile(self, outFile):
        if os.path.exists(os.path.join(os.curdir, outFile)):
            index = 0
            while True:
                index += 1
                filename = "%s.%d" % (outFile, index)
                if not os.path.exists(os.path.join(os.curdir, filename)):
                    break
            os.rename(outFile, filename)

    ''' Initialize an console logging handler with the provided 'level' as logging level '''
    def _loggingInit(self, level):
        root = self._getLog()
        root.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.level = level
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        root.addHandler(ch)


    ''' Retrieve a logger with the fully qualified name of this class '''
    def _getLog(self):
        return logging.getLogger(__name__)

    ''' Load a text file into a string and returns it.
        If 'filePath' is None or an empty string, it does nothing and return an empty string. '''
    def _loadFile(self, filePath):
        fileContent = ""
        if filePath:
            fileToLoad = open(filePath, 'r')
            fileContent = fileToLoad.read()
            fileToLoad.close()
        return fileContent

    ''' Resize the image according to the provided size, then uploads it on the
        remote image hosting site. Returns the direct link to the resized image.
        @param imageFilePath The absolute path to the image file.
        @param imageSize A tuple containing (width, height) in pixels.
        @return None when the provided image has an unknown image format.
        @remark Raises an ImageUploaderException exception in the following cases:
                -if the provided 'imageFilePath' is not a recognized image format. 
                -whenever the backend class throws an exception'''
    def _remoteImageCreate(self, imageFilePath, imageSize):
        self._getLog().debug(("opening {0}").format(imageFilePath))
        image = None
        try:
            image = Image.open(imageFilePath)
            for orientation in ExifTags.TAGS.keys() :
                if ExifTags.TAGS[orientation]=='Orientation' : break
            lExif = image._getexif()
            if(lExif):
                exif=dict(lExif.items())
                if orientation in exif:
                    if exif[orientation] == 3 :
                        image=image.rotate(180, expand=True)
                    elif exif[orientation] == 6 :
                        image=image.rotate(270, expand=True)
                    elif exif[orientation] == 8 :
                        image=image.rotate(90, expand=True)
        except IOError:
            raise ImageUploaderException("{0} is not an image file.".format(imageFilePath))

        self._getLog().debug(("resizing... {0}").format(imageFilePath))
        image = image.resize((imageSize[0],
            int(image.size[1] / (image.size[0] / float(imageSize[0])))), Image.ANTIALIAS)
        saveFilePath = os.path.join(self._tmpDirectory, imageFilePath)
        image.save(saveFilePath)
        self._getLog().debug(("saved {0} !").format(imageFilePath))
        self._getLog().debug(("uploading {0} with size {1}.").format(imageFilePath, imageSize))

        try:
            #Creates the class as specified by the _backendClass class member.
            hostingServerInterface = self._backendClass()
            hostingServerInterface.setClientId(self._oauthClientId)
            hostingServerInterface.setSecret(self._oauthSecret)
            return hostingServerInterface.uploadImage(saveFilePath)
        except Exception as pExc:
            raise ImageUploaderException("Unexpected error occurred during backend execution: '{0}'".format(pExc))
        
    ''' Given the URL link to the thumb and to the actual image, it returns an HTML
        code that displays the thumb and open in a new tab the actual image when the thumb is clicked.'''
    def _createImageLink(self, imageLink, thumbLink):
        image_link_template = "<a target=\"_blank\" href=\"{0}\"><img alt=\"Click here to enlarge the image!\" src=\"{1}\"></a>"
        return image_link_template.format(imageLink, thumbLink)

        '''
            Create in the _sourceImageDirectory directory the HTML file
            '''
    def _generateHTMLFile(self):
        self._renameExistingFile(self._outputHTMLFilename)
        headerString = ""
        try:
            headerString = self._loadFile(self._htmlHeaderFilePath)
        except IOError as err:
            self._getLog().warning("Cannot use header HTML file '{0}' due to: {1}".format(self._htmlHeaderFilePath, str(err)));
        footerString = ""
        try:
            footerString = self._loadFile(self._htmlFooterFilePath)
        except IOError as err:
            self._getLog().warning("Cannot use footer HTML file '{0}' due to: {1}".format(self._htmlFooterFilePath, str(err)));

        with open(os.path.join(os.curdir, self._outputHTMLFilename), "wb") as outputFile:
            outputFile.write(bytes(headerString, 'UTF-8'))
            for i in lImageTracker.getImageList():
                outputFile.write(bytes(self._createImageLink(i.getURLFullImage(), i.getURLThumbImage()), 'UTF-8'))
                outputFile.write(bytes("&nbsp;", 'UTF-8'))
            outputFile.write(bytes(footerString, 'UTF-8'))
        self._getLog().info("Image gallery generated into \"{0}\".".format(self._outputHTMLFilename))

    '''Collects all files in the given directory, return the list of identified image type files.
    '''
    def getImagesList(pDirectory):
        lImageFiles = []
        lFiles = [f for f in os.listdir(pDirectory) if os.path.isfile(os.path.join(pDirectory, f))]
        for lImageFilePath in lFiles:
            lImage = None
            try:
                lImage = Image.open(lImageFilePath)
                lImageFiles.append(lImageFilePath)
            except Exception as e:
                pass #Skip any non-image file.
            finally:
                del lImage #Clean up any acquired resources.
        return lImageFiles
    
    ''' Iterates over all files in the configured path and upload
        all the files that represent a recognized image format. Then it creates an HTML file
        containing a gallery of the uploaded images.
    '''
    def uploadImagesAndCreateHTMLGallery(self, pUploadedImagesTracker):
        try:
            lImages = ImageUploader.getImagesList(self._sourceImageDirectory)
            for imageFileName in lImages:
                try:
                    '''
                    Skip any file already processed (i.e. already present into the lock file).
                    '''
                    if(pUploadedImagesTracker.isImageAlreadyUploaded(imageFileName)):
                        self._getLog().info("Skipped already uploaded file {0}.".format(str(imageFileName)))
                    else:
                        self._getLog().info("Processing file {0} ...".format(str(imageFileName)))
                        lImageFullPath = os.path.join(self._sourceImageDirectory, imageFileName)
                        URLFullImage = self._remoteImageCreate(lImageFullPath, self._targetImageSize)
                        self._getLog().info("uploaded full image for {0}".format(str(imageFileName)))
                        URLThumbImage = self._remoteImageCreate(lImageFullPath, self._thumbImageSize)
                        self._getLog().info("uploaded thumb image for {0}.".format(str(imageFileName)))
                        pUploadedImagesTracker.addUploadedImage(imageFileName, URLFullImage, URLThumbImage)
                except ImageUploaderException as e:
                    self._getLog().warning("skipping file {0} for error: {1}".format(str(imageFileName), str(e)))

            self._generateHTMLFile()
                    
        except UploadedImagesTrackerException as e:
            #//## TODO HACK The exception below should be casted upon some value coming from the exception catched.
            # Here instead it is just casted, whatever the catched exception is.
            raise ImageUploaderException("Another instance of the script is running in the same directory \"{0}\"".format(self._sourceImageDirectory))


'''=========================================================='''
'''                   M    A    I    N                       '''
'''=========================================================='''
if __name__ == "__main__":
    try:
        '''Parsing of the input on command line. '''
        parser = ArgumentParser()
        parser.add_argument('-c', '--console-log-level', metavar='ARG',
            action='store', dest='console_log',
            default=None,
            help='Adds a console logger for the level specified in the range 1..50')
        args = parser.parse_args()
        logLevel = getConsoleLevel(args.console_log)


        try:
            ''' Create the image uploader. '''
            imgUp = ImageUploader(os.getcwd(), logLevel)
            ''' Launch the process acquiring exclusive access to the lock file '''
            with UploadedImagesTracker(imgUp.getImageSourceDirectory()) as lImageTracker:
                ''' Upload all the image files in the provided image directory and generate the HTML output image gallery.'''
                imgUp.uploadImagesAndCreateHTMLGallery(lImageTracker)
        except UploadedImagesTrackerLockAcquiringFailed as pExc:
            print("Another instance of imguploader is running: %s" % (pExc))
            
    except Exception as ex:
        ''' Regarding the activity log file, nothing has to be done here since it is assumed that any outstanding
        lock is released by the OS upon exit. '''
        print("Unexpected error occurred, details follows:")
        print("Traceback: {0}".format(traceback.print_exc()))
        print("Unexpected error that stopped script execution: {0}".format(str(ex)))

