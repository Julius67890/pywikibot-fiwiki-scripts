# Purpose: add structured data to pictures from finna
#
# Running script: python <scriptname>

import pywikibot
import mwparserfromhell
import json
from urllib.request import urlopen

import urllib.parse

import re
import urllib
import requests
import imagehash
import io
import os
import tempfile
from PIL import Image

import urllib3


# ----- FinnaData

#class FinnaData:
# Find (old) finna id's from file page urls
def get_finna_ids(page):
    finna_ids=[]

    for url in page.extlinks():
        if "finna.fi" in url:
            id = None

            # Parse id from url
            patterns = [
                           r"finna\.fi/Record/([^?]+)",
                           r"finna\.fi/Cover/Show\?id=([^&]+)",
                           r"finna\.fi/thumbnail\.php\?id=([^&]+)",
                           r"finna\.fi/Cover/Download\?id=([^&]+)",
                       ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    id = match.group(1)
                    if id not in finna_ids:
                        finna_ids.append(id)
                    break

    return finna_ids

# urlencode Finna parameters
def finna_api_parameter(name, value):
   return "&" + urllib.parse.quote_plus(name) + "=" + urllib.parse.quote_plus(value)


# Get finna API record with most of the information
# Finna API documentation
# * https://api.finna.fi
# * https://www.kiwi.fi/pages/viewpage.action?pageId=53839221 

def get_finna_record(id):

    url="https://api.finna.fi/v1/record?id=" +  urllib.parse.quote_plus(id)
    url+= finna_api_parameter('field[]', 'id')
    url+= finna_api_parameter('field[]', 'title')
    url+= finna_api_parameter('field[]', 'subTitle')
    url+= finna_api_parameter('field[]', 'shortTitle')
    url+= finna_api_parameter('field[]', 'summary')
    url+= finna_api_parameter('field[]', 'imageRights')
    url+= finna_api_parameter('field[]', 'images')
    url+= finna_api_parameter('field[]', 'imagesExtended')
    #url+= finna_api_parameter('field[]', 'onlineUrls')
    url+= finna_api_parameter('field[]', 'openUrl')
    url+= finna_api_parameter('field[]', 'nonPresenterAuthors')
    url+= finna_api_parameter('field[]', 'onlineUrls')
    url+= finna_api_parameter('field[]', 'subjects')
    #url+= finna_api_parameter('field[]', 'subjectsExtendet')
    url+= finna_api_parameter('field[]', 'subjectPlaces')
    url+= finna_api_parameter('field[]', 'subjectActors')
    url+= finna_api_parameter('field[]', 'subjectDetails')
    # url+= finna_api_parameter('field[]', 'geoLocations')
    url+= finna_api_parameter('field[]', 'buildings')
    url+= finna_api_parameter('field[]', 'identifierString')
    url+= finna_api_parameter('field[]', 'collections')
    url+= finna_api_parameter('field[]', 'institutions')
    url+= finna_api_parameter('field[]', 'classifications')
    url+= finna_api_parameter('field[]', 'events')
    url+= finna_api_parameter('field[]', 'languages')
    url+= finna_api_parameter('field[]', 'originalLanguages')
    url+= finna_api_parameter('field[]', 'year')
    #url+= finna_api_parameter('field[]', 'hierarchicalPlaceNames')
    url+= finna_api_parameter('field[]', 'formats')
    #url+= finna_api_parameter('field[]', 'physicalDescriptions')
    url+= finna_api_parameter('field[]', 'measurements')

    try:
        response = requests.get(url)
        return response.json()
    except:
        print("Finna API query failed: " + url)
        exit(1)

# convert string to base 16 integer for calculating difference
def converthashtoint(h, base=16):
    return int(str(h), base)

# Compares if the image is same using similarity hashing
# method is to convert images to 64bit integers and then
# calculate hamming distance. 
#
# Perceptual hashing 
# http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html
# difference hashing
# http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html
#
def is_same_image(img1, img2, hashlen=8):

    phash1 = imagehash.phash(img1, hash_size=hashlen)
    dhash1 = imagehash.dhash(img1, hash_size=hashlen)
    phash1_int = converthashtoint(phash1)
    dhash1_int = converthashtoint(dhash1)

    phash2 = imagehash.phash(img2, hash_size=hashlen)
    dhash2 = imagehash.dhash(img2, hash_size=hashlen)
    phash2_int = converthashtoint(phash2)
    dhash2_int = converthashtoint(dhash2)

    # Hamming distance difference
    phash_diff = bin(phash1_int ^ phash2_int).count('1')
    dhash_diff = bin(dhash1_int ^ dhash2_int).count('1') 

    # print hamming distance
    if (phash_diff == 0 and dhash_diff == 0):
        print("Both hashes are equal")
    else:
        print("Phash diff: " + str(phash_diff) + ", image1: " + str(phash1) + ", image2: " + str(phash2))
        print("Dhash diff: " + str(dhash_diff) + ", image1: " + str(dhash1) + ", image2: " + str(dhash2))

    # max distance for same is that least one is 0 and second is max 3

    if phash_diff == 0 and dhash_diff < 4:
        return True
    elif phash_diff < 4 and dhash_diff == 0:
        return True
    else:
        return False

def convert_tiff_to_jpg(tiff_image):
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as fp:
        tiff_image.convert('RGB').save(fp, "JPEG", quality=95)
    return fp.name    

# note: commons at least once has thrown error due to client policy?
# "Client Error: Forbidden. Please comply with the User-Agent policy"
# keep an eye out for problems..
def downloadimage(url):
    headers={'User-Agent': 'pywikibot'}
    # Image.open(urllib.request.urlopen(url, headers=headers))

    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
                            
    return Image.open(io.BytesIO(response.content))

# ----- /FinnaData

# strip id from other things that may be after it:
# there might be part of url or some html in same field..
def stripid(oldsource):
    # space after url?
    indexend = oldsource.find(" ")
    if (indexend > 0):
        oldsource = oldsource[:indexend]

    # html tag after url?
    indexend = oldsource.find("<")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find(">")
    if (indexend > 0):
        oldsource = oldsource[:indexend]

    # wikimarkup after url?
    indexend = oldsource.find("[")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find("]")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find("{")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find("}")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find("|")
    if (indexend > 0):
        oldsource = oldsource[:indexend]

    # some parameters in url?
    indexend = oldsource.find("&")
    if (indexend > 0):
        oldsource = oldsource[:indexend]
    indexend = oldsource.find("#")
    if (indexend > 0):
        oldsource = oldsource[:indexend]

    # some parameters in url?
    indexend = oldsource.find("?")
    if (indexend > 0):
        oldsource = oldsource[:indexend]

    # linefeed at end?
    if (oldsource.endswith("\n")):
        oldsource = oldsource[:len(oldsource)-1]

    return oldsource

# link might have "show?id=<id>" which we handle here
# if it has "Record/<id>" handle it separately
def getlinksourceid(oldsource):
    strlen = len("id=")
    indexid = oldsource.find("id=")
    if (indexid < 0):
        return ""
    oldsource = oldsource[indexid+strlen:]
    return stripid(oldsource)

def getrecordid(oldsource):
    strlen = len("/Record/")
    indexid = oldsource.find("/Record/")
    if (indexid < 0):
        return ""
    oldsource = oldsource[indexid+strlen:]
    return stripid(oldsource)
    
# commons source may have human readable stuff in it
# parse to plain url
def geturlfromsource(source):
    protolen = len("http://")
    index = source.find("http://")
    if (index < 0):
        protolen = len("https://")
        index = source.find("https://")
        if (index < 0):
            # no url in string
            return ""

    # try to find space or something            
    indexend = source.find(" ", index+protolen)
    if (indexend < 0):
        # no space or other clear separator -> just use string length
        indexend = len(source)-1
        
    return source[index:indexend]

# input: kuvakokoelmat.fi url
# output: old format id
def getkuvakokoelmatidfromurl(source):
    indexlast = source.rfind("/", 0, len(source)-1)
    if (indexlast < 0):
        # no separator found?
        print("invalid url: " + source)
        return ""
    kkid = source[indexlast+1:]
    if (kkid.endswith("\n")):
        kkid = kkid[:len(kkid)-1]

    indexlast = kkid.rfind(".", 0, len(source)-1)
    if (indexlast > 0):
        # .jpg or something at end? remove id
        kkid = kkid[:indexlast]
    return kkid

# input: old format "HK"-id, e.g. HK7155:219-65-1
# output: newer "musketti"-id, e.g. musketti.M012%3AHK7155:219-65-1
def convertkuvakokoelmatid(kkid):
    if (len(kkid) == 0):
        print("empty kuvakokoelmat id ")
        return ""

    # verify
    if (kkid.startswith("HK") == False and kkid.startswith("JOKA") == False
        and kkid.startswith("SUK") == False and kkid.startswith("SMK") == False 
        and kkid.startswith("KK") == False 
        and kkid.startswith("1") == False):
        print("does not start appropriately: " + kkid)
        return ""

    if (kkid.startswith("HK") == True):
        index = kkid.find("_")
        if (index < 0):
            print("no underscores: " + kkid)
            return ""
        # one underscore to colon
        # underscores to dash
        # add prefix
        kkid = kkid[:index] + ":" + kkid[index+1:]
        kkid = kkid.replace("_", "-")

    if (kkid.startswith("JOKA") == True):
        # if there is one underscore -> set to colon
        #kkid = kkid.replace("_", ":")
        # if there is two -> only set the latter one to colon and leave first as underscore
        indexlast = kkid.rfind("_", 0, len(kkid)-1)
        if (indexlast > 0):
            kkid = kkid[:indexlast] + ":" + kkid[indexlast+1:]

    if (kkid.startswith("SUK") == True):
        kkid = kkid.replace("_", ":")

    if (kkid.startswith("SMK") == True):
        kkid = kkid.replace("_", ":")

    if (kkid.startswith("KK") == True):
        kkid = kkid.replace("_", ":")

    if (kkid.startswith("1") == True):
        kkid = "HK" + kkid
        kkid = kkid.replace("_", ":")

    # url may have something else in it -> remove it
    kkid = leftfrom(kkid, "#")

    musketti = "musketti.M012:" + kkid
    return musketti

# if there's garbage in id, strip to where it ends
def leftfrom(string, char):
    index = string.find(char)
    if (index > 0):
        return string[:index]

    return string

# parse Q-code from link
def getqcodefromwikidatalink(target):
    targetqcode = str(target)
    index = targetqcode.find(":")
    if (index < 0):
        return ""
    indexend = targetqcode.find("]", index)
    if (indexend < 0):
        return ""
    targetqcode = targetqcode[index+1:indexend]
    return targetqcode
    
# parse claims or statements from commons SDC
def getcollectiontargetqcode(statements, collections):
    if "P195" not in statements:
        return collections
    
    claimlist = statements["P195"]
    for claim in claimlist:
        # target is expected to be like: [[wikidata:Q118976025]]
        target = claim.getTarget()

        # parse Q-code from link
        targetqcode = getqcodefromwikidatalink(target)

        # no need to add if SDC-data already has a target
        # -> remove from collections to add
        if (targetqcode in collections):
            collections.remove(targetqcode)

        # TODO: finish comparison to wikidata:
        # -might belong to multiple collections -> multiple entries
        # -might have something that isn't in finna list
        # -might be missing something that is in finna list -> should add to commons SDC
        #if (target not in collections):
        # claim.removetarget..

        #dataitem = pywikibot.ItemPage(wikidata_site, "Q118976025")
        # check item, might belong to multiple collections -> compare to list from finna

    # debug
    #print("final collections are: " + str(collections))

    # return list of those to be added
    return collections

# is license in statements
#P275, "CC BY 4.0" is Q20007257
def islicenseinstatements(statements, license):
    if (license != "CC BY 4.0"):
        # bug? we only support one license currently
        return False
    if "P275" not in statements:
        return False
    claimlist = statements["P275"]    
    for claim in claimlist:
        target = claim.getTarget()
        targetqcode = getqcodefromwikidatalink(target)
        if (targetqcode == "Q20007257"):
            return True
        #else:
            # may have multiple licenses, just ignore (cc by sa/nc..)
            #print("License is NOT as expected, Q-code: " + targetqcode)

    return False

#P854, sourceurl
def addlicensetostatements(pywikibot, wikidata_site, license, sourceurl):
    if (license != "CC BY 4.0"):
        # bug? we only support one license currently
        return False

    licqcode = "Q20007257"
    claim_licp = 'P275'  # property ID for "license"
    lic_claim = pywikibot.Claim(wikidata_site, claim_licp)
    qualifier_targetlic = pywikibot.ItemPage(wikidata_site, licqcode)
    lic_claim.setTarget(qualifier_targetlic)
    
    # note: this add qualifer but we want "reference" type
    qualifier_url = pywikibot.Claim(wikidata_site, 'P854')  # property ID for source URL (reference url)
    qualifier_url.setTarget(sourceurl)
    lic_claim.addSource(qualifier_url, summary='Adding reference URL qualifier')
    # is there "addreference()"?
    
    return lic_claim

# TODO: check if 'P275' is missing 'P854' as reference url
def checklicensesources(statements, sourceurl):
    if "P275" not in statements:
        print("license property not in statements")
        return False

    # note: there may be more than on license per item (not equal)
    # so check source is under appropriate license..
    claimlist = statements["P275"]    
    for claim in claimlist:
        target = claim.getTarget()
        targetqcode = getqcodefromwikidatalink(target)
        if (targetqcode != "Q20007257"): # not our license
            #print("DEBUG: unsupported license: " + targetqcode)
            continue
    
        sourcelist = claim.getSources()
        for source in sourcelist:
            for key, value in source.items():
                for v in value: # v is another claim..
                    vtarget = v.getTarget()
                    if (vtarget == sourceurl):
                        matchfound = True
                        print("license source found")
                        return True
        print("license source not found, url: " + sourceurl)
    return False

def isidinstatements(statements, newid):
    if "P9478" not in statements:
        return False
    claimlist = statements["P9478"]    
    for claim in claimlist:
        # target is expected to be like: "musketti." or "museovirasto."
        target = claim.getTarget()
        if (target == newid):
            # match found: no need to add same ID again
            return True

    # ID not found -> should be added
    return False

def addfinnaidtostatements(pywikibot, wikidata_site, finnaid):
    claim_finnaidp = 'P9478'  # property ID for "finna ID"
    finna_claim = pywikibot.Claim(wikidata_site, claim_finnaidp)
    # url might have old style id as quoted -> no need with new id
    finnaunquoted = urllib.parse.unquote(finnaid)
    finna_claim.setTarget(finnaunquoted)
    return finna_claim

def addcollectiontostatements(pywikibot, wikidata_site, collection):
    claim_collp = 'P195'  # property ID for "collection"
    coll_claim = pywikibot.Claim(wikidata_site, claim_collp)
    qualifier_targetcoll = pywikibot.ItemPage(wikidata_site, collection)
    coll_claim.setTarget(qualifier_targetcoll)
    return coll_claim

# https&#x3A;&#x2F;&#x2F;api.finna.fi&#x2F;v1&#x2F;record&#x3F;id&#x3D;
def parseapiidfromfinnapage(finnapage):
    index = finnapage.find(';api.finna.fi&')
    if (index < 0):
        return ""
    finnapage = finnapage[index:]        

    index = finnapage.find('id')
    if (index < 0):
        return ""
    index = finnapage.find('&#x3D;')
    if (index < 0):
        return ""
    index = index + len("&#x3D;")
    finnapage = finnapage[index:]

    indexend = finnapage.find('"')
    if (indexend < 0):
        indexend = finnapage.find('>')
        if (indexend < 0):
            return ""
    finnapage = finnapage[:indexend]
    
    # convert html code to character (if any)
    finnapage = finnapage.replace("&#x25;3A", ":")
    
    indexend = finnapage.find('&amp')
    if (indexend < 0):
        indexend = finnapage.find('&')
        if (indexend < 0):
            return ""
    finnapage = finnapage[:indexend]
    return finnapage

def parsedatarecordidfromfinnapage(finnapage):
    attrlen = len('data-record-id="')
    indexid = finnapage.find('data-record-id="')
    if (indexid < 0):
        return ""
        
    indexid = indexid+attrlen
    indexend = finnapage.find('"', indexid)
    if (indexend < 0):
        return ""

    return finnapage[indexid:indexend]

# fetch metapage from finna and try to parse current ID from the page
# since we might have obsolete ID.
# new ID is needed API query.
def parsemetaidfromfinnapage(finnaurl):

    finnapage = ""

    try:
        request = urllib.request.Request(finnaurl)
        print("request done: " + finnaurl)

        response = urllib.request.urlopen(request)
        if (response.readable() == False):
            print("response not readable")

        htmlbytes = response.read()
        finnapage = htmlbytes.decode("utf8")

        #print("page: " + finnapage)
        
    except urllib.error.HTTPError as e:
        print(e.__dict__)
        return ""
    except urllib.error.URLError as e:
        print(e.__dict__)
        return ""
    #except:
        #print("failed to retrieve finna page")
        #return ""

    # try a new method to parse the id..
    newid = parseapiidfromfinnapage(finnapage)
    if (len(newid) > 0):
        # sometimes finna has this html code instead of url encoding..
        newid = newid.replace("&#x25;3A", ":")
        print("new id from finna: " + newid)
        return newid

    newid = parsedatarecordidfromfinnapage(finnapage)
    if (len(newid) > 0):
        # in case there is url encoding in place..
        #newid = newid.replace("%3A", ":")
        print("new id from finna: " + newid)
        return newid

    return ""
    
def getnewsourceforfinna(finnarecord):
    return "<br>Image record page in Finna: [https://finna.fi/Record/" + finnarecord + " " + finnarecord + "]\n"

# get pages immediately under cat
# and upto depth of 1 in subcats
def getcatpages(pywikibot, commonssite, maincat, recurse=False):
    final_pages = list()
    cat = pywikibot.Category(commonssite, maincat)
    pages = list(commonssite.categorymembers(cat))

    for page in pages:
        if page not in final_pages:
            final_pages.append(page)

    # no recursion by default, just get into depth of 1
    if (recurse == True):
        subcats = list(cat.subcategories())
        for subcat in subcats:
            subpages = commonssite.categorymembers(subcat)
            for subpage in subpages:
                if subpage not in pages: # avoid duplicates
                    final_pages.append(page)

    return final_pages

def getlinkedpages(pywikibot, commonssite, linkpage):
    listpage = pywikibot.Page(commonssite, linkpage)  # The page you're interested in

    pages = list()
    # Get all linked pages from the page
    for linked_page in listpage.linkedPages():
        if linked_page not in pages: # avoid duplicates
            pages.append(linked_page)

    return pages

# brute force check if wikibase exists for structured data:
# need to add it manually for now if it doesn't
def doessdcbaseexist(page):
    try:
        wditem = page.data_item()  # Get the data item associated with the page
        #if (wditem.exists() == False):
        data = wditem.get() # all the properties in json-format
        return True # no exception -> ok, we can use it
    except:
        print("failed to retrieve structured data")

    return False

# ------ main()

# TODO: check wikidata for correct qcodes
# 
# qcode of collections -> label
d_qcodetolabel = dict()
d_qcodetolabel["Q118976025"] = "Studio Kuvasiskojen kokoelma"
d_qcodetolabel["Q107388072"] = "Historian kuvakokoelma" # /Museovirasto/Historian kuvakokoelma/
d_labeltoqcode = dict()
d_labeltoqcode["Studio Kuvasiskojen kokoelma"] = "Q118976025"
d_labeltoqcode["Historian kuvakokoelma"] = "Q107388072" # /Museovirasto/Historian kuvakokoelma/

# Accessing wikidata properties and items
wikidata_site = pywikibot.Site("wikidata", "wikidata")  # Connect to Wikidata

# site = pywikibot.Site("fi", "wikipedia")
commonssite = pywikibot.Site("commons", "commons")
commonssite.login()

# get list of pages upto depth of 1 
#pages = getcatpages(pywikibot, commonssite, "Category:Kuvasiskot", True)
#pages = getcatpages(pywikibot, commonssite, "Professors of University of Helsinki", True)
#pages = getlinkedpages(pywikibot, commonssite, 'user:FinnaUploadBot/filelist')
pages = getlinkedpages(pywikibot, commonssite, 'User:FinnaUploadBot/kuvakokoelmat.fi')

#pages = getcatpages(pywikibot, commonssite, "Botanists from Finland")

rowcount = 1
#rowlimit = 10

print("Pages found: " + str(len(pages)))

for page in pages:
    # 14 is category -> recurse into subcategories
    #
    if page.namespace() != 6:  # 6 is the namespace ID for files
        continue

    filepage = pywikibot.FilePage(page)
    if filepage.isRedirectPage():
        continue
    file_info = filepage.latest_file_info

    oldtext=page.text

    print(" ////////", rowcount, ": [ " + page.title() + " ] ////////")
    rowcount += 1

    #site = pywikibot.Site("wikidata", "wikidata")
    #repo = site.data_repository()
    #item = pywikibot.ItemPage(repo, "Q2225")    
    
    wikicode = mwparserfromhell.parse(page.text)
    templatelist = wikicode.filter_templates()

    # should store new format id to picture source
    # -> use setfinnasource.py for these for now
    #addFinnaIdForKuvakokoelmatSource = False

    kkid = ""
    finnaid = ""
    finnasource = ""
    for template in wikicode.filter_templates():
        # at least three different templates have been used..
        if template.name.matches("Information") or template.name.matches("Photograph") or template.name.matches("Artwork") or template.name.matches("Art Photo"):
            if template.has("Source"):
                par = template.get("Source")
                srcvalue = str(par.value)
                if (srcvalue.find("kuvakokoelmat.fi") > 0):
                    kkid = getkuvakokoelmatidfromurl(srcvalue)
                if (srcvalue.find("finna.fi") > 0):
                    finnasource = srcvalue
                    finnaid = getlinksourceid(srcvalue)
                    if (finnaid == ""):
                        finnaid = getrecordid(srcvalue)
                        if (finnaid == ""):
                            print("no id and no record found")
                        break

            if template.has("source"):
                par = template.get("source")
                srcvalue = str(par.value)
                if (srcvalue.find("kuvakokoelmat.fi") > 0):
                    kkid = getkuvakokoelmatidfromurl(srcvalue)
                if (srcvalue.find("finna.fi") > 0):
                    finnasource = srcvalue
                    finnaid = getlinksourceid(srcvalue)
                    if (finnaid == ""):
                        finnaid = getrecordid(srcvalue)
                        if (finnaid == ""):
                            print("no id and no record found")
                        break

    if (len(finnaid) == 0 and len(kkid) > 0):
        finnaid = convertkuvakokoelmatid(kkid)
        finnaid = urllib.parse.quote(finnaid) # quote for url
        print("Converted old id in: " + page.title() + " from: " + kkid + " to: " + finnaid)
        # TODO: update source information to include new id
        # -> use setfinnasource.py for now
        #addFinnaIdForKuvakokoelmatSource = True

    if (len(finnaid) == 0):
        # urls coming from wikidata instead of in page?
        finna_ids = get_finna_ids(page)
        if (len(finna_ids) >= 1):
            print("NOTE: " + page.title() + " has external urls but not in expected place")
            # might have something usable..
        else:
            print("Could not find a finna id in " + page.title() + ", skipping.")
        continue
 
    # kuvasiskot has "musketti" as part of identier, alternatively "museovirasto" may be used in some cases
    if (finnaid.find("musketti") < 0 and finnaid.find("museovirasto") < 0):
        print("WARN: unexpected id in: " + page.title() + ", id: " + finnaid)
        #continue
    if (finnaid.find("profium.com") > 0):
        print("WARN: unusable url (redirector) in: " + page.title() + ", id: " + finnaid)
        continue
        
    if (len(finnaid) >= 50):
        print("WARN: finna id in " + page.title() + " is unusually long? bug or garbage in url? ")
    if (len(finnaid) <= 5):
        print("WARN: finna id in " + page.title() + " is unusually short? bug or garbage in url? ")
    if (finnaid.find("?") > 0 or finnaid.find("&") > 0 or finnaid.find("<") > 0 or finnaid.find(">") > 0 or finnaid.find("#") > 0 or finnaid.find("[") > 0 or finnaid.find("]") > 0 or finnaid.find("{") > 0 or finnaid.find("}") > 0):
        print("WARN: finna id in " + page.title() + " has unexpected characters, bug or garbage in url? ")
        
        # remove strange charaters and stuff after if any
        finnaid = stripid(finnaid)
        print("note: finna id in " + page.title() + " is " + finnaid)


    if (finnaid.find("\n") > 0):
        print("WARN: removing newline from: " + page.title())
        finnaid = leftfrom(finnaid, "\n")
        
    if (finnaid.endswith("\n")):
        print("WARN: finna id in " + page.title() + " ends with newline ")
        finnaid = finnaid[:len(finnaid)-1]

    print("finna ID found: " + finnaid)
    sourceurl = "https://www.finna.fi/Record/" + finnaid

    if (finnaid.find("musketti") >= 0 or finnaid.find("hkm.HKM") >= 0):
        # check if the source has something other than url in it as well..
        # if it has some human-readable things try to parse real url
        if (len(finnasource) > 0):
            finnaurl = geturlfromsource(finnasource)
            if (finnaurl == ""):
                print("WARN: could not parse finna url from source in " + page.title() + ", source: " + finnasource)
                #continue
    
        # obsolete id -> try to fetch page and locate current ID
        finnaid = parsemetaidfromfinnapage(sourceurl)
        if (finnaid == ""):
            print("WARN: could not parse current finna id in " + page.title() + " , skipping, url: " + sourceurl)
            continue
        if (finnaid.find("\n") > 0):
            finnaid = leftfrom(finnaid, "\n")
            print("WARN: removed newline from new finna id for: " + page.title() + ", " + finnaid )
           
        if (finnaid.find("museovirasto.") == 0 or finnaid.find("hkm.") == 0):
            print("new finna ID found: " + finnaid)
            sourceurl = "https://www.finna.fi/Record/" + finnaid
        else:
            print("WARN: unexpected finna id in " + page.title() + ", id from finna: " + finnaid)
            #continue

    finna_record = get_finna_record(finnaid)
    if (finna_record['status'] != 'OK'):
        print("Skipping (status not OK): " + finnaid + " status: " + finna_record['status'])
        continue

    if (finna_record['resultCount'] != 1):
        print("Skipping (result not 1): " + finnaid + " count: " + str(finna_record['resultCount']))
        continue

    print("finna record ok: " + finnaid)

    if "records" not in finna_record:
        print("WARN: 'records' not found in finna record, skipping: " + finnaid)
        continue
    if (len(finna_record['records']) == 0):
        print("WARN: empty array of 'records' for finna record, skipping: " + finnaid)
        continue
    if "collections" not in finna_record['records'][0]:
        print("WARN: 'collections' not found in finna record, skipping: " + finnaid)
        continue

    # collections: expecting ['Historian kuvakokoelma', 'Studio Kuvasiskojen kokoelma']
    finna_collections = finna_record['records'][0]['collections']

    #if ("Antellin kokoelma" in finna_collections):
        #print("Skipping collection (can't match by hash due similarities): " + finnaid)
        #continue
    
    collectionqcodes = list()
    # lookup qcode by label TODO: fetch from wikidata 
    for coll in finna_collections:
        if coll in d_labeltoqcode:
            collectionqcodes.append(d_labeltoqcode[coll])

    if "imagesExtended" not in finna_record['records'][0]:
        print("WARN: 'imagesExtended' not found in finna record, skipping: " + finnaid)
        continue

    # Test copyright (old field: rights, but request has imageRights?)
    # imageRights = finna_record['records'][0]['imageRights']
    imagesExtended = finna_record['records'][0]['imagesExtended'][0]
    if (imagesExtended['rights']['copyright'] != "CC BY 4.0"):
        print("Incorrect copyright: " + imagesExtended['rights']['copyright'])
        continue

    # 'images' can have array of multiple images, need to select correct one
    # -> loop through them (they should have just different &index= in them)
    # and compare with the image in commons
    imageList = finna_record['records'][0]['images']

    match_found = False
    if (len(imageList) == 1):
        # get image from commons for comparison:
        # try to use same size
        commons_image_url = filepage.get_file_url()
        commons_image = downloadimage(commons_image_url)
    
        finna_image_url = "https://finna.fi" + imagesExtended['urls']['large']
        finna_image = downloadimage(finna_image_url)
        
        # Test if image is same using similarity hashing
        if (is_same_image(finna_image, commons_image) == True):
            match_found = True

    if (len(imageList) > 1):
        # multiple images in finna related to same item -> 
        # need to pick the one that is closest match
        print("Multiple images for same item: " + str(len(imageList)))

        # get image from commons for comparison:
        # try to use same size
        commons_image_url = filepage.get_file_url()
        commons_image = downloadimage(commons_image_url)
        
        f_imgindex = 0
        for img in imageList:
            finna_image_url = "https://finna.fi" + img
            finna_image = downloadimage(finna_image_url)

            # Test if image is same using similarity hashing
            if (is_same_image(finna_image, commons_image) == True):
                match_found = True
                need_index = True
                print("Matching image index: " + str(f_imgindex))
                break
            else:
                f_imgindex = f_imgindex + 1

    if (match_found == False):
        print("No matching image found, skipping: " + finnaid)
        continue

    #item = pywikibot.ItemPage.fromPage(page) # can't use in commons, no related wikidata item
    # note: data_item() causes exception if wikibase page isn't made yet, see for an alternative
    # repo == site == commonssite
    #testitem = pywikibot.ItemPage(commonssite, 'Q1') # test something like this?
    if (doessdcbaseexist(page) == False):
        print("Wikibase item does not yet exist for: " + page.title() + ", id: " + finnaid)
        continue
    wditem = page.data_item()  # Get the data item associated with the page
    data = wditem.get() # all the properties in json-format
    
    if "statements" not in data:
        print("No statements found for claims: " + finnaid)
        continue
    claims = data['statements']  # claims are just one step from dataproperties down

    flag_add_source = False
    flag_add_collection = False
    flag_add_finna = False

    claim_sourcep = 'P7482'  # property ID for "source of file"
    if claim_sourcep not in claims:
        # P7482 "source of file" 
        item_internet = pywikibot.ItemPage(wikidata_site, 'Q74228490')  # file available on the internet
        source_claim = pywikibot.Claim(wikidata_site, claim_sourcep)
        source_claim.setTarget(item_internet)
    
        # P973 "described at URL"
        qualifier_url = pywikibot.Claim(wikidata_site, 'P973')  # property ID for "described at URL"
        qualifier_url.setTarget(sourceurl)
        source_claim.addQualifier(qualifier_url, summary='Adding described at URL qualifier')

        # P137 "operator"
        qualifier_operator = pywikibot.Claim(wikidata_site, 'P137')  # Replace with the property ID for "operator"
        qualifier_targetop = pywikibot.ItemPage(wikidata_site, 'Q420747')  # National Library of Finland (Kansalliskirjasto)
        qualifier_operator.setTarget(qualifier_targetop)
        source_claim.addQualifier(qualifier_operator, summary='Adding operator qualifier')

        # P123 "publisher"
        # Q3029524 Finnish Heritage Agency (Museovirasto)
        qualifier_publisher = pywikibot.Claim(wikidata_site, 'P123')  # property ID for "publisher"
        qualifier_targetpub = pywikibot.ItemPage(wikidata_site, 'Q3029524')  # Finnish Heritage Agency (Museovirasto)
        qualifier_publisher.setTarget(qualifier_targetpub)
        source_claim.addQualifier(qualifier_publisher, summary='Adding publisher qualifier')

        commonssite.addClaim(wditem, source_claim)
        flag_add_source = True
    else:
        print("no need to add source")

    # is license in statements
    #P275, "CC BY 4.0" is Q20007257
    #P854, sourceurl
    if (islicenseinstatements(claims, "CC BY 4.0") == False):
        print("NOTE: license missing or not same in statements")
        lic_claim = addlicensetostatements(pywikibot, wikidata_site, "CC BY 4.0", sourceurl)
        commonssite.addClaim(wditem, lic_claim)
    else:
        print("license found in statements, OK")
        if (checklicensesources(claims, sourceurl) == False):
            print("license source not found in statements")
        else:
            print("license source found in statements, OK")

    # check SDC and try match with finna list collectionqcodes
    collectionstoadd = getcollectiontargetqcode(claims, collectionqcodes)
    if (len(collectionstoadd) > 0):
        print("adding statements for collections: " + str(collectionstoadd))

        # Q118976025 "Studio Kuvasiskojen kokoelma"
        for collection in collectionstoadd:
            coll_claim = addcollectiontostatements(pywikibot, wikidata_site, collection)

            # batching does not work correctly with pywikibot:
            # need to commit each one
            commonssite.addClaim(wditem, coll_claim)
            
        flag_add_collection = True
    else:
        print("no need to add collections")

    # if the stored ID is not same (new ID) -> add new
    if (isidinstatements(claims, finnaid) == False):
        print("adding finna id to statements: " + finnaid)
        
        finna_claim = addfinnaidtostatements(pywikibot, wikidata_site, finnaid)
        commonssite.addClaim(wditem, finna_claim)
        flag_add_finna = True
    else:
        print("id found, not adding again")

    if (flag_add_source == False and flag_add_collection == False and flag_add_finna == False):
        print("Nothing to add, skipping.")
        continue

    #pywikibot.info('----')
    #pywikibot.showDiff(oldtext, newtext,2)
    #summary='Adding structured data to file'
    #pywikibot.info('Edit summary: {}'.format(summary))

    #question='Do you want to accept these changes?'
    #choice = pywikibot.input_choice(
    #            question,
    #            [('Yes', 'y'),('No', 'N'),('Quit', 'q')],
    #            default='N',
    #            automatic_quit=False
    #        )

    #pywikibot.info(choice)
    #if choice == 'q':
    #    print("Asked to exit. Exiting.")
    #    exit()

    #if choice == 'y':
        # script setfinnasource is used for this
        #if (addFinnaIdForKuvakokoelmatSource == True):
            #page.text=newtext
            #page.save(summary)
        
        # batching does not work correctly with pywikibot
        #if (flag_add_source == True):
            #commonssite.addClaim(wditem, source_claim)
        #if (flag_add_collection == True):
            #commonssite.addClaim(wditem, coll_claim)
        #if (flag_add_finna == True):
            #commonssite.addClaim(wditem, finna_claim)

    # don't try too many at once
    #if (rowcount >= rowlimit):
    #    print("Limit reached")
    #    exit(1)
    #    break

