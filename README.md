#imguploader: a script to upload files to online image hosting services
=======================================================================

Author: Luca Cappa (lcappa@gmail.com)

License: GNU General Public License version 3 or any later version

The main task of the script is to generate an HTML file containing
an image gallery.

The script needs to have a wellformed configuration file stored in a file called *.imguploader.cfg*

The script is subdivided into:

1. an unique frontend implemented into the ImageUploader class;
2. several backends (for example the ImgurBackend class), i.e. classes that take care of uploading the images to an hosting service.

The frontend accomplishes the following tasks:

1. parse and validate command line arguments;
2. parse and validate configuration file;
3. enumerate and identify image files;
4. keep track of already uploaded image and restart the uploading from where it was interrupted;
5. provide feedback to the user.

The backends have to accomplish the following tasks:

1. Upload images to the online image hosting service;
2. Report back to the frontend of any useful information or error.

## Installation

No installation procedure is actually implemented, you just need to checkout the whole content of the repository, copy it somewhere, and know what are you doing :P
Nevertheless your contribution by providing a package for any Python software management repository is welcome.

## Script usage
How to use the script in short:

* Edit appropriately the configuration file *.imguploader.cfg*.
* Open a terminal window.
* Change directory into the directory containing the images to be uploaded:

>terminal_prompt> cd /path/to/image/directory/

* Run the script:

>terminal_prompt> python /path/to/where/you/copied/the/script/imguploader.py


## Script inner working details
The first action of the script is to open the configuration file (called *.imguploader.cfg*)
 from the home directory of the user launching it, otherwise if not found from the current directory.
Then it parses and validates the content of the configuration file. If the configuration file
 is not found or the content is malformed, the scripts just bails out.

Notably in the configuration the following list of values must be set a value for the following keys:
* Under the *[config]* section:
  * hostingServerBackendClass
  * tmpDirPath
  * oauthClientId
  * oauthSecret

The script iterates over all the files in the current directory (where it is launched from),
and for each of them determines whether it is an image data file or not: in the latter case
the file is just skipped, in the former the file path is designated to be included in the
image gallery. 

Each image file is resized according to the configuration file (*targetImageWidthPx* key and its key friends)
, and then it is uploaded by using the selected class (*hostingServerBackendClass* key) to the online image hosting service.

Eventually the script generates an HTML file (named according to the key *outputHTMLFilename*) in the current directory containing an image gallery of the uploaded images. The output is created by putting at the beginning of the file the content of the file indicated by the *HTMLHeaderFilePath* key, then the image gallery is dynamically created, and then the end of the file contains the content of the file specified by the *HTMLFooterFilePath* key.

The content of HTML file can be copied and pasted into wherever you need to: for example 
it is useful in order to show the gallery of images on the listing of an item you are selling
online.


## The .imguploader.cfg configuration file

This file is stored either in the home directory of the user launching the script, either in the
current directory where the script has been launched.
Its format is like an INI file, i.e. each line contains a single *"key=value"* pair.
All the keys must be under the section called 'config', like this:

>[config]

>key1=value1

>key2=value2

* Keys of the configuration file in the 'config' section:

  * hostingServerBackendClass: the string containing the name of the class that is delegated the job of uploading the images to the online image hosting service. It is mandatory.

  * oauthClientId: your OAuth client id. Usually any hosting service requires OAuth authentication. It is mandatory.

  * oauthSecret: your OAuth secret. Usually any hosting service requires OAuth authentication. It is mandatory.

  * tmpDirPath: the absolute path to a directory where temporary image files are stored. It is mandatory.

  * HTMLFooterFilePath: the absolute path to the file that contains the footer HTML code of the generated HTML 
output file. It is optional, default value is empty.

  * HTMLHeaderFilePath: the absolute path to the file that contains the header HTML code of the generated HTML 
output file. It is optional, default value is empty.

  * targetImageWidthPx: width in pixel of the image uploaded. It is optional, default value is 1280.

  * targetImageHeightPx: height in pixel of the image uploaded. It is optional, default value is 1280.

  * thumbImageWidthPx: width in pixel of the thumb image uploaded. It is optional, default value is 320.

  * thumbImageHeightPx: height in pixel of the thumb image uploaded. It is optional, default value is 320.

  * outputHTMLFilename: the name of the generated HTML file. It is optional, default value is 'listing.html'.


## The imgbackends.py module

This module must contain the definition of the classes used to upload files to an online image hosting
service. This class can be called as the 'backend' for image uploading, as the frontend is all contained into the imguploader.py module (it in ImageUploader class, guessed it, eh?). It contains the definition of the interface class ImageHostingServerBackendInterface that must be inherited from by any class that is to be used by the hostingServerBackendClass key.

At the moment this module contains one single class, ImgurBackend, that is used to upload images 
to the Imgur hosting service. 
Feel free to contribute by providing any further implementation of the interface for any other hosting service.

## Real world example of usage of this script

Suppose you want to sell something on eBay (registered trademark of eBay Inc.), you can take several pictures of your item and put all of them in a directory. Now open a terminal, and from that directory launch the command:

> terminal_prompt> python /path/to/where/you/copied/the/script/imguploader

At the end of its execution, in the same directory there will be generated an HMTL file. Just open it, copy the content of it, and paste it into the Details/HTML text area of the eBay listing. That's all!

If you want to have an already customized HTML output, you could leverage the *HTMLHeaderFilePath* key by pointing it to a file containing the following barebone HTML code:

```
<style type="text/css">
<!-- PUT HERE ANY HTML STYLES YOU WANT. YOU CAN REUSE IT IN YOUR CUSTOM HTML CODE -->
</style>
I am selling the following item: PUT HERE THE DESCRIPTION OF YOUR ITEM
<h3>Pictures</h3>
<table>
```

And the *HTMLFooterFilePath* pointing to a file containing:

```
</table>
```
