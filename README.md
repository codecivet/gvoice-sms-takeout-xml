# gvoice-sms-takeout-xml
Convert Google Voice SMS data from Takeout to .xml suitable for use with SMS Backup and Restore.
Input data is a folder of SMS .html files from Google Takeout.

Working as of May 2, 2022.

I do not plan to support this. This was a one-off to get my data transferred from Google Voice. I
hope this can help someone who might try this in the future, like calyptecc and brismuth's great
work helped me. Thanks so much to them! Please feel free to fork this.

## Improvements from brismuth fork
* Support for images (jpg and gif tested, should work with png)
* Timestamps were off for me. This is fixed.
* Added `requirements.txt` so that dependency versions are known good.
* Text formatting may be improved. For example, there is support for `<br>` tags now. It's possible
  there are also some text output regressions from my changes.
* The header creation uses much less memory. My environment choked on header creation with a 1.5GB
  output file without my improvements.
* Should work pretty reliably without the (Optional) steps below. I put in a bunch of stuff to work
  around issues with missing phone numbers.
* Tested on my 1.5GB archive of 75000 messages. There are a lot of corner cases handled now. It runs
  completely autonomously on my archive without any hacking or workarounds.

## Issues
* In conversations with a single person (ie SMS conversations), messages with images will often
  be restored with text that wasn't visible initially, such as "MMS sent" and "MMS received." This
  is probably an easy fix, but I didn't discover it until after restoring to my phone, so I did not
  tackle it.
* Having seen so many potential corner cases and inconsistencies in the Google Takeout archive 
  format, I guarantee there are cases I have missed. I'm hoping that the size of my archive means
  I've found a good number of them.
* I improved error handling which helped development a lot, but this probably means the script can 
  terminate on errors more easily than the other forks. This might frustrate people who just want it
  to run and don't care if errors are bypassed and some data is lost.
* Videos are not supported. Who is going to take on that one?? 😆

## How to use:
1. (Optional) Export all Google Contacts
1. (Optional) Delete all Google Contacts (this is causes numbers show up for each thread, otherwise 
   Takeout will sometimes only have names. If you want to skip this step, you can, but some messages 
   won't be linked to the right thread if you do. Note that this may remove Contact Photos on iOS if 
   you don't pause syncing on your iOS device)
1. Get Google Voice Takeout and download
1. (Optional) Restore contacts to your account
1. Clone this repo to your computer. Downloading sms.py and requirements.txt should also work.
1. Extract Google Voice Takeout and move the folder into the same folder as this script
1. Open terminal
1. Install python
1. Install pip
1. Create virtual environment (`python -m venv .venv`)
1. Activate virtual environment (`.venv\Scripts\activate.bat` or `source .venv/bin/activate`)
1. Install dependencies (`python -m pip install -r requirements.txt`)
1. `python sms.py`
1. Copy the file `gvoice-all.xml` to your phone, then restore from it using SMS Backup and Restore



