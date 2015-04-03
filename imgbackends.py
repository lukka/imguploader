import os
import sys

'''Get the directory where this script is'''
def getScriptDirectory():
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

''' Add to the sys.path the path to the Imgur Python module directory. '''
sys.path.append(os.path.join(getScriptDirectory(), "imgur-python"))

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError
from imgurpython.helpers.error import ImgurClientRateLimitError
import imguploader


''' The interface any image uploading backend implementation must adhere to. '''
class ImageHostingServerBackendInterface:
    ''' Upload the image on the image hosting server.'''
    def uploadImage(self, pathToImageFile):
        raise NotImplementedError

    ''' Set the secret of OAuth '''
    def setSecret(self, secret):
        raise NotImplementedError

    ''' Set the client id for OAuth '''
    def setClientId(self, clientId):
        raise NotImplementedError

    ''' Return the descriptive name of the backend used for image hosting'''
    def getDescriptiveName(self):
        raise NotImplementedError

''' The concrete implementation of the image uploading backend for Imgur.com.
'''
class ImgurBackend(ImageHostingServerBackendInterface):

    ''' The name of the parameter for the client id for OAuth'''
    _IMGUR_JSON_CLIENT_ID_PARAM = "client_id"
    ''' The name of the parameter for the secret for OAuth'''
    _IMGUR_JSON_SECRET_PARAM = "secret"

    ''' The name of the parameter of the uploaded URL. '''
    _IMGUR_RETURNED_URL_PARAM = "link"

    ''' Ctor '''
    def __init__(self):
        self._imgurClient = None
        self._oauthSecret = None
        self._oauthClientId = None

    ''' Upload the image to imgur.com
        Return None when an error occurred
        Return the URL to the uploaded image if uploading succeeded.
    '''
    def uploadImage(self, pathToImageFile):
        try:
            returnedImageLink = None
            if pathToImageFile:
                self._imgurClient = ImgurClient(self._oauthClientId, self._oauthSecret)

                response = self._imgurClient.upload_from_path(pathToImageFile)
                if response != None and ImgurBackend._IMGUR_RETURNED_URL_PARAM in response:
                    returnedImageLink = response[ImgurBackend._IMGUR_RETURNED_URL_PARAM]
            return returnedImageLink
        except ImgurClientRateLimitError as exc:
            raise imguploader.ImageUploaderException("Rate limit exceeded ({0})!".format(exc))
        except ImgurClientError as exc:
            raise imguploader.ImageUploaderException("Error occurred while uploading image ({0})!".format(exc))

    ''' Set the secret for OAuth '''
    def setSecret(self, secret):
        self._oauthSecret = secret

    ''' Set the client id for OAuth '''
    def setClientId(self, clientId):
        self._oauthClientId = clientId

    def getDescriptiveName(self):
        return "Imgur backend"

