import sys
import os
'''Get the directory where this script is'''
def getScriptDirectory():
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
''' Add to the sys.path the path to the Imgur Python module directory. '''
sys.path.append(os.path.join(getScriptDirectory(), "../imgur-python"))
import imgurpython
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch
import imguploader
import traceback 
from importlib import import_module
from PIL import Image

# Used to mock the Image.open() behavior
def raiseIfNotImageTypeFile(a):
    #Succeed for a filename that ends with jpg or png, fail for everything else raising an exception.
    # It resembles remotely the behavior of Image.open().
    if (not (a.endswith("jpg") or a.endswith("png"))):
        raise Exception()

class TestSuite_ImgUploader(unittest.TestCase):

    def test_getConsoleLevel(self):
        assert(imguploader.getConsoleLevel(None) == imguploader.CONSOLE_DEFAULT_LEVEL)
        assert(imguploader.getConsoleLevel("ciccio") == imguploader.CONSOLE_DEFAULT_LEVEL)
        assert(imguploader.getConsoleLevel("") == imguploader.CONSOLE_DEFAULT_LEVEL)
        assert(imguploader.getConsoleLevel("11") == 11)
        assert(imguploader.getConsoleLevel(0) == 0)
        assert(imguploader.getConsoleLevel(4000000) == 4000000)
        assert(imguploader.getConsoleLevel(4000) == 4000)
        assert(imguploader.getConsoleLevel(400) == 400)
        assert(imguploader.getConsoleLevel(40) == 40)

    def test_UploadedImage(self):
        fileName = "fileName"
        full = "full"
        thumb = "thumb"
        assert(imguploader.UploadedImage(fileName, full, thumb).getImageFileName() == fileName)
        assert(imguploader.UploadedImage(fileName, full, thumb).getURLFullImage() == full)
        assert(imguploader.UploadedImage(fileName, full, thumb).getURLThumbImage() == thumb)

    @patch("imguploader.open", create=True)
    @patch("fcntl.flock", return_value=None)
    def test_UploadedImagesTracker(self, pMockForOpen, pMockForFlock):
        #Test assertion raised when flock fails.
        mocked_open = mock_open()
        with patch("imguploader.open", mocked_open, create=True):
            with patch("fcntl.flock", MagicMock(side_effect=IOError)):
                self.assertRaises(imguploader.UploadedImagesTrackerLockAcquiringFailed, imguploader.UploadedImagesTracker, "directory")

        #Test assertion raised when the activity log file is corrupted.
        mocked_open = mock_open(read_data="noooooooooooo")
        with patch("imguploader.open", mocked_open, create=True):
            with patch("fcntl.flock", MagicMock(return_value=None)):
                self.assertRaises(imguploader.UploadedImagesTrackerException, imguploader.UploadedImagesTracker, "directory")

        #Test proper construction of the UploadedImagesTracker.getImageList() returned list.
        mocked_open = mock_open(read_data="fileName<URLfull<URLthumb")
        with patch("imguploader.open", mocked_open, create=True):
            with patch("fcntl.flock", MagicMock(return_value=None)):
                entry = imguploader.UploadedImagesTracker("directory")
                assert(entry.getImageList()[0].getImageFileName() == "fileName")
                assert(entry.isImageAlreadyUploaded("fileName") == True)
                
        #Test for proper call to close() on the activity log file.
        lOpenMocked = mock_open(read_data="")
        with patch("imguploader.open", lOpenMocked, create=True):
            with imguploader.UploadedImagesTracker("directory"):
                pass
        lOpenMocked().close.assert_called_once_with()

        #Test for UploadedImagesTracker.addUploadedImage()
        uploadedImagesTracker = imguploader.UploadedImagesTracker("directory")
        uploadedImagesTracker.addUploadedImage("imageFileName", "FullURL", "ThumbURL")
        assert(uploadedImagesTracker._uploadedImages[0].getImageFileName() == "imageFileName")
        assert(uploadedImagesTracker._uploadedImages[0].getURLFullImage() == "FullURL")
        assert(uploadedImagesTracker._uploadedImages[0].getURLThumbImage() == "ThumbURL")


    @patch("imguploader.open", create=True)
    @patch("fcntl.flock", return_value=None)
    def test_ImageUploader(self, pMockForOpen, pMockForFlock):
        print("test_ImageUploader()<<")
        #Test for exception raised when no config file is found.
        imguploader.ImageUploader._CFG_CONFIG_FILE_NAME = "this_file_cannot_exists_right_huh"
        self.assertRaises(imguploader.ImageUploaderException, imguploader.ImageUploader, ".")

        #Test for correctness of ImageUploader.getImagesList()
        # Simulate the presence of 'first.jpg' and 'second.png' along a bunch of non-image files.
        with patch('os.listdir', MagicMock(return_value = ['first.jpg', 'second.png', 'info.txt', 'error.log',
            "amiga.iff", "core.dump", "armour.bld", "third.png"])) as lListDirMock:
            with patch('os.path.isfile', MagicMock(return_value=True)) as lIsFileMock:
                with patch('PIL.Image.open', side_effect=raiseIfNotImageTypeFile) as lImageOpenMock:
                    lImageList = imguploader.ImageUploader.getImagesList('fasfsas')
                    self.assertEqual(lImageList, ["first.jpg", "second.png", 'third.png'])

        # Test for 'connection aborted' casted by 
        #         response = method_to_call(url, headers=header, data=data)
        # in file imguploader/imgur-python/imgurpython/client.py", line 124, in make_request
        # The imguploader.ImageUploader class must catch it and cast an appropriate imguploader.ImageUploaderException.
        print("connection aborted casted test:<<")
        imguploader.ImageUploader._parseValidateConfigurationFile = MagicMock(return_value = True)
        imguploader.ImageUploader._renameExistingFile = MagicMock()
        with patch('imgurpython.ImgurClient', autospec=True) as lImgurClientMock:
            lImageMock = MagicMock()
            lImageMock._getexif.return_value = None
            with patch('PIL.Image.open', return_value=lImageMock) as lImageOpenMock:
                lImgurClientMock.upload_from_path = MagicMock(side_effect=Exception)
                lImgUp = imguploader.ImageUploader("/fake/path", 1)
                imguploader.ImageUploader.getImagesList = MagicMock(return_value=["xxx.jpg"])
                lImgUp._generateHTMLFile = MagicMock()
                #Set the ImageUploader._backendClass private var member that is not set as _parseValidationConfigurationFile is mocked.
                lBackendsModule = import_module("imgbackends")
                lImgUp._backendClass = getattr(lBackendsModule, "ImgurBackend")
                lImgUp._backendClass.uploadImage = MagicMock(side_effect=Exception())
                lImgTracker = MagicMock()
                lImgTracker.isImageAlreadyUploaded.return_value = False;
                #assert not raises:
                lImgUp.uploadImagesAndCreateHTMLGallery(lImgTracker)
            
        print("test_ImageUploader()>>")
        
