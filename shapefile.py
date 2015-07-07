'''
Python:
	accept epsg as argument

	copy into new DB
	create structure for 3nf
	add geometry columns
	Call Ruby:
		Write responses into 3nf
	write geometries into 3nf tables

	call shapefile tool


	TODO:
		convert ruby calls into rbenv or system ruby calls
		figure out how shell script wrapper needs to work for exporter


'''


import sqlite3
import csv, codecs, cStringIO
from xml.dom import minidom
import sys
import pprint
import glob
import json
import os
import shutil
import re
import zipfile
import subprocess
import glob
import tempfile

print sys.argv

def upper_repl(match):
	if (match.group(1) == None):
		return ""
	return match.group(1).upper()

def clean(str):
	 out = re.sub(" ([a-z])|[^A-Za-z0-9]+", upper_repl, str)	 
	 return out

originalDir = sys.argv[1]
exportDir = tempfile.mkdtemp()+"/"
finalExportDir = sys.argv[2]+"/"
importDB = originalDir+"db.sqlite3"
exportDB = exportDir+"shape.sqlite3"
jsondata = json.load(open(originalDir+'module.settings'))
srid = jsondata['srid']
arch16nFile = glob.glob(originalDir+"*.0.properties")[0]
print jsondata
moduleName = clean(jsondata['name'])

def zipdir(path, zip):
    for root, dirs, files in os.walk(path):
        for file in files:
            zip.write(os.path.join(root, file))


try:
    os.remove(exportDB)
except OSError:
    pass

importCon = sqlite3.connect(importDB)
importCon.enable_load_extension(True)
importCon.load_extension("libspatialite.so.5")
exportCon = sqlite3.connect(exportDB)
exportCon.enable_load_extension(True)
exportCon.load_extension("libspatialite.so.5")


exportCon.execute("select initSpatialMetaData(1)")
'''
for line in importCon.iterdump():
	try:
		exportCon.execute(line)
	except sqlite3.Error:		
		pass
'''		




  
exportCon.execute("create table keyval (key text, val text);")

f = open(arch16nFile, 'r')
for line in f:
	
	keyval = line.replace("\n","").replace("\r","").decode("utf-8").split('=')
	keyval[0] = '{'+keyval[0]+'}'
	exportCon.execute("insert into keyval(key, val) VALUES(?, ?)", keyval)
f.close()







for aenttypeid, aenttypename in importCon.execute("select aenttypeid, aenttypename from aenttype"):	
	aenttypename = clean(aenttypename)
	attributes = ['identifier', 'createdBy', 'createdAtGMT', 'modifiedBy', 'modifiedAtGMT']
	for attr in importCon.execute("select attributename from attributekey join idealaent using (attributeid) where aenttypeid = ? order by aentcountorder", [aenttypeid]):
		attrToInsert = clean(attr[0])

		attributes.append(attrToInsert)
	attribList = " TEXT, \n\t".join(attributes)
	createStmt = "Create table %s (\n\tuuid TEXT PRIMARY KEY,\n\t%s TEXT);" % (aenttypename, attribList)
	
	exportCon.execute(createStmt)

geometryColumns = []
for row in importCon.execute("select aenttypename, geometrytype(geometryn(geospatialcolumn,1)) as geomtype, count(distinct geometrytype(geometryn(geospatialcolumn,1))) from latestnondeletedarchent join aenttype using (aenttypeid) where geomtype is not null group by aenttypename having  count(distinct geometrytype(geometryn(geospatialcolumn,1))) = 1"):
	geometryColumns.append(row[0])
	geocolumn = "select addGeometryColumn('%s', 'geospatialcolumn', %s, '%s', 'XY');" %(row[0],srid,row[1]);
	
	exportCon.execute(geocolumn)





for aenttypename, uuid, createdAt, createdBy, modifiedAt, modifiedBy,geometry in importCon.execute("select aenttypename, uuid, createdAt || ' GMT', createdBy, datetime(modifiedAt) || ' GMT', modifiedBy,transform(geometryn(geospatialcolumn,1),%s) from latestnondeletedarchent join aenttype using (aenttypeid) join createdModifiedAtBy using (uuid) order by createdAt" % (srid)):
	
	if (aenttypename in geometryColumns):		
		insert = "insert into %s (uuid, createdAtGMT, createdBy, modifiedAtGMT, modifiedBy, geospatialcolumn) VALUES(?, ?, ?, ?, ?, ?)" % (clean(aenttypename))
		exportCon.execute(insert, [str(uuid), createdAt, createdBy, modifiedAt, modifiedBy, geometry])
	else:
		insert = "insert into %s (uuid, createdAtGMT, createdBy, modifiedAtGMT, modifiedBy) VALUES(?, ?, ?, ?, ?)" % (clean(aenttypename))
		exportCon.execute(insert, [str(uuid), createdAt, createdBy, modifiedAt, modifiedBy])



try:
    os.remove(exportDir+'shape.out')
except OSError:
    pass


subprocess.call(["bash", "./format.sh", originalDir, exportDir])



updateArray = []
f= open(exportDir+'shape.out', 'r')
for line in f.readlines():
	out = line.replace("\n","").split("\t")
	if (len(out) ==4):		
		update = "update %s set %s = '%s' where uuid = %s;" % (clean(out[1]), clean(out[2]), out[3].replace("'","''"), out[0])
		exportCon.execute(update)




exportCon.commit()

files = ['shape.sqlite3']
for row in importCon.execute("select aenttypename, geometrytype(geometryn(geospatialcolumn,1)) as geomtype, count(distinct geometrytype(geometryn(geospatialcolumn,1))) from latestnondeletedarchent join aenttype using (aenttypeid) where geomtype is not null group by aenttypename having  count(distinct geometrytype(geometryn(geospatialcolumn,1))) = 1"):
	cmd = ["spatialite_tool", "-e", "-shp", "%s" % (row[0].decode("ascii")), "-d", "%sshape.sqlite3" % (exportDir), "-t", "%s" % (row[0]), "-c", "utf-8", "-g", "geospatialcolumn", "-s", "%s" % (srid), "--type", "%s" % (row[1])]
	files.append("%s.dbf" % (row[0]))
	files.append("%s.shp" % (row[0]))
	files.append("%s.shx" % (row[0]))
	print cmd
	subprocess.call(cmd, cwd=exportDir)

for at in importCon.execute("select aenttypename from aenttype"):
	aenttypename = "%s" % (clean(at[0]))
	cursor = exportCon.cursor()
	cursor.execute("select * from %s" % (aenttypename))	
	files.append("Entity-%s.csv" % (aenttypename))
	csv_writer = csv.writer(open(exportDir+"Entity-%s.csv" % (aenttypename), "wb+"))
	csv_writer.writerow([i[0] for i in cursor.description]) # write headers
	csv_writer.writerows(cursor)
	#spatialite_tool -e -shp surveyUnitTransectBuffer -d db.sqlite3 -t surveyUnitWithTransectBuffer -c utf-8 -g surveyBuffer --type polygon


relntypequery = '''select distinct relntypeid, relntypename from relntype join latestnondeletedrelationship using (relntypeid);'''

relnquery = '''select parent.uuid as fromuuid, child.uuid as touuid, fname || ' ' || lname as username, parent.aentrelntimestamp, parent.participatesverb from (select * from latestnondeletedaentreln join relationship using (relationshipid)  where relationshipid in (select relationshipid from relationship join relntype using (relntypeid) where relntypename = ?)) parent join (latestnondeletedaentreln join relationship using (relationshipid)) child on (parent.relationshipid = child.relationshipid and parent.uuid != child.uuid)  join user using (userid)'''


relntypecursor = importCon.cursor()
relncursor = importCon.cursor()
for relntypeid, relntypename in relntypecursor.execute(relntypequery): 
	relncursor.execute(relnquery, [relntypename])
	files.append("Relationship-%s.csv" % (clean(relntypename)))
	csv_writer = csv.writer(open(exportDir+"Relationship-%s.csv" % (clean(relntypename)), "wb+"))
	csv_writer.writerow([i[0] for i in relncursor.description]) # write headers
	csv_writer.writerows(relncursor)


zipf = zipfile.ZipFile("%s/%s-export.zip" % (finalExportDir,moduleName), 'w')
for file in files:
    zipf.write(exportDir+file, moduleName+'/'+file)
zipf.close()

try:
    os.remove(exportDir)
except OSError:
    pass