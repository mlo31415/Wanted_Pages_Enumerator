import tkinter as tk
from tkinter import filedialog
import zipfile
import time
import WikidotHelpers.WikidotHelpers as WikidotHelpers

log = open("log.txt", "w")


# *****************************************************************
# Should this filename be ignored?
# This routine is highly wiki-dependent
# Return value is either the cleaned filename or None if the file should be ignored.
def InterestingFilenameZip(filenameZip):

    if not filenameZip.startswith("source/"):    # We're only interested in source files
        return None
    if len(filenameZip) <= 11:  # There needs to be something there besides just 'source/.txt'
           return None

    # These files are specific to Fancyclopedia and are known to be ignorable
    if filenameZip.startswith("source/deleted_"):   # Ignore deleted pages
        return None
    if filenameZip.startswith("source/nav_"):   # Ignore navigation pages
        return None
    if filenameZip.startswith("source/forum_"):   # Ignore forum pages
        return None
    if filenameZip.startswith("source/testing_"):   # These are test pages of various sorts
        return None
    if filenameZip.startswith("source/system_"):   # Ignore system pages
        return None
    if filenameZip.startswith("source/admin_"):   # Ignore system admin pages
        return None
    if filenameZip.startswith("source/search_"):   # Ignore system search pages
        return None
    if filenameZip.startswith("source/index_"):   # Ignore our index pages
        return None

    return filenameZip[7:-4]  # Drop "source/" and ".txt", returning the cleaned name


# *****************************************************************
# *****************************************************************
# Main
# Navigate to zipped backup file to be analyzed, open it, and read it
root = tk.Tk()
root.withdraw()
zipFilepath = filedialog.askopenfilename()
if not zipfile.is_zipfile(zipFilepath):
    exit()
zip = zipfile.ZipFile(zipFilepath)

# redirects is a dictionary of redirects.  The key is a cannonicized name, the value is the cannonicized name that it is redirected to.
redirects = {}

pageChildren = {}   # Dictionary of pageChildren. The key is the cannonicized page name. The value is a list of cannonicized pages referred to on that page
countPages=0        # Count of all pages with content, including redirects
pagesNames=[]       # List of cannonicized page names

# Walk through the zip file, looking only at source pages.
zipEntryNames = zip.namelist()
for zipEntryName in zipEntryNames:
    nameZip=InterestingFilenameZip(zipEntryName)
    if nameZip == None:
        continue
    source = WikidotHelpers.ReadPageSourceFromZip(zip, zipEntryName)
    if source == None:
        continue

    countPages += 1
    nameZip=WikidotHelpers.ConvertZipCategoryMarker(nameZip)
    pagesNames.append(WikidotHelpers.Cannonicize(nameZip)) # Create the list of all cannonicized, interesting names: Both content pages and redirects

    # Is this a redirect?
    redir = WikidotHelpers.IsRedirect(source)
    if redir != None:
        # If so, add it to the redirect dictionary (remember to remove the extension!)
        name=WikidotHelpers.Cannonicize(nameZip)
        if name == redir:  # Skip circular redirects
            continue
        redirects[name] = redir
        continue

countRedirects=len(redirects)
countPages=len(pagesNames)
# Now we need to trace all the redirect chains  and make sure that every redirect points to the end of its chain.
# I.e., right now we have a->b, b->c.  We want this to be a->c and b->c.
for n in redirects:
    while redirects.get(redirects[n]) != None:  # Is the page we're redirecting to also a redirect?
        redirects[n] = redirects[redirects[n]]

print("Redirects analysis complete: redirects.len=", countRedirects)

# Next we go through the *non*-redirect pages and create a list of their references
pagesRefs = {}  # The dictionary of pages, each holding a list of references for that page
refsPages = {}  # The dictionary of references, each holding a list of pages that reference it
countContentPages=0
for zipEntryName in zipEntryNames:
    uncanName=InterestingFilenameZip(zipEntryName)
    name=WikidotHelpers.Cannonicize(uncanName)
    if name == None:
        continue
    if redirects.get(name) != None:  # Skip redirects
        continue

    # Load the page source
    source = WikidotHelpers.ReadPageSourceFromZip(zip, zipEntryName)  # Skip empty pages
    if source == None or len(source) == 0:
        print("error: Page '"+zipEntryName+"' is empty.", file=log)
        continue

    # We need to find all the references in the page.  A reference is a string inside a pair of triple square brackets, i.e., [[[string]]]
    # We'll start by spliting the page on "[[[". This will yield a list of strings, each starting with a reference which ends with "]]]", usually followed by junk.
    splitSource = source.split("[[[")
    refs = []       # Refs will be a list of all the references found in this source page
    for r in splitSource:
        if r.find("]]]") < 1:   # If the string doesn't contain reference closing brackets ("]]]"), then it's a leading string of junk which must be skipped.
            continue
        ref = r.split("]]]")    # If it does contain "]]]", then there's a reference to be found.  The format of the string is <reference>]]]<trailing stuff>.
        if ref == None or len(ref) <= 1:    # If there's nothing to be found, skip it.
            continue
        if ref[0] != None and len(ref) > 0: # The part we want ("<reference>" from the comment above) will be in ref[0].  Make sure it exists.
            if ref[0].find("|") > 0:    # Look for references containing "|".  These are of the form <reference name>|<display name>.  We want just the reference name.
                ref[0]=ref[0][:ref[0].find("|")]
            if ref[0].find("http:") > 0:    # We don't want references which are actually outside Wikidot
                continue
            refCan=WikidotHelpers.Cannonicize(ref[0])
            refs.append(refCan)
            WikidotHelpers.AddUncannonicalName(ref[0], refCan)

    countContentPages += 1

    # Take all the references we've collected from this source page, make sure any redirects are followed, and update the refPages dict.
    # RefsPages[name] contains a list of all pages which refer *to* the source pages "name".
    rrefs = []
    for r in refs:  # r is a reference to another page contained in page n
        if redirects.get(r) == None:    # Make sure each ref is fully redirected
            rrefs.append(r)
        else:
            rrefs.append(redirects[r])

        if refsPages.get(r) == None:
            refsPages[r]=[]
        refsPages[r].append(name)

    # PagesRefs[name], OTOH, contains a list of all pages referred to by source page "name"
    pagesRefs[name] = rrefs

print("Source reference analysis complete:", len(pagesRefs), "pages found with references")

# We now have a list of all content pages and each of those pages has a list of pages referenced
# We want to gather some statistics and make some lists of interesting pages:
# * How many pages total? (names.len())
# * How many content pages?  (names.len()-redirects.len())
# * How many redirects?     (redirects.len())
# * How many references total?
# * How many missing pages?
# * List of all missing pages references 10 or more times
# * List of most referenced pages

# We need to count the number of references each page has.
countTotalRefs = 0
countRefs = {}  # A dictionary of pages with reference counts for that page
for name in pagesNames:
    if pagesRefs.get(name) != None:
        for r in pagesRefs[name]:
            if countRefs.get(r) == None:
                countRefs[r] = 0
            countRefs[r] += 1
            countTotalRefs += 1

# It's output time!
# We'll prepend the file name with the date.  Get the date string
day=time.strftime("%Y-%m-%d")

# Summary statistics
file=open(day+" Summary Statistics.txt", "w")
print("||||~ Summary Statistics ||", file=file)
print("||~ Kind ||~ Number ||~ Notes ||", file=file)
print("|| Pages with content ||", countContentPages, "|| All pages that have text on them. ||", file=file)
print("|| Redirects ||", countRedirects, "|| Pages which redirect to a content page. (The content page itself does not necessarily yet exist.) ||", file=file)
print("|| Total existing pages ||", countPages, "|| Pages with content plus redirects ||", file=file)
print("|| Pages still needed ||", len(refsPages)-countContentPages-countRedirects, "|| Pages which are referred to, but which have not yet been created ||", file=file)
print("|| Total references ||", countTotalRefs, "|| A count of how many links to other pages exist in all existing pages ||", file=file)
file.close()

# Most Referenced Pages
file=open(day+" Most Referenced Pages.txt", "w")

# We generate one line in the table for each *value* of reference count (i.e., all pages with 50 references are in a single row of the table.)
# First sort countRefs into descending order.  To do this, we turn it into a list of tuples(name, count)
countRefTuples = []
for name in countRefs:
    countRefTuples.append((name, countRefs[name]))
countRefTuples.sort(key=lambda n: n[1], reverse=True)

currentNum=-1
line=""
for crt in countRefTuples:
    if crt[1] != currentNum:
        if len(line)>0:
            print("||", currentNum, "||", line, "||", file=file)
            line=""
        currentNum=crt[1]

    if currentNum <= 7:
        break

    if len(crt[0]) == 4 and crt[0].isdecimal() and (crt[0].startswith("19") or crt[0].startswith("20")):
        continue    # Skip the year entries
    if len(line)>0:
        line=line+", "  # The first entry is not preceded by a comma
    line=line+"[[["+WikidotHelpers.Uncannonicize(crt[0])+"]]]"

file.close()

# Most requested pages
file=open(day+" Most Wanted Pages.txt", "w")

# Go through the dictionary and copy just the tuples missing pages.
missingPages=[]
for crt in countRefTuples:
    if pagesRefs.get(crt[0]) == None:
        missingPages.append(crt)

# Sort what's left
missingPages.sort(key=lambda n: n[1], reverse=True)

# We generate one line in the table for each *value* of reference count (i.e., all pages with 50 references are listed in a single row of the table.)
currentNum=-1
line=""
for mp in missingPages:
    if mp[1] != currentNum:
        if len(line)>0:
            print("||", currentNum, "||", line, "||", file=file)
            line=""
        currentNum=mp[1]

    if currentNum <= 5:
        break

    if len(line)>0:
        line=line+", "
    line=line+"[[["+WikidotHelpers.Uncannonicize(mp[0])+"]]]"

file.close()

# Print the list of all references
file=open(day+" Pages.txt", "w")
for name in pagesNames:
    print(WikidotHelpers.Uncannonicize(name), file=file)
file.close()

exit

