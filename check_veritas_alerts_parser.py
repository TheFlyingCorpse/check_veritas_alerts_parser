#!/usr/bin/env python3


#################################################
# Veritas NetBackup Appliance Alerts XML parser #
# Written by Rune Darrud           2020-02-04   #
#################################################

import sys
import xmltodict
import argparse
import traceback

from datetime import datetime, timezone

returncode = 4
unknownOutput = list()
criticalOutput = list()
warningOutput = list()
output = list()
perfdataList = list()
outputSummary = str()

parser = argparse.ArgumentParser()
parser.add_argument("--verbose", help="Increase output verbosity")
parser.add_argument("--xmlfile", help="Path to the Veritas Alerts XML file")
parser.add_argument("--appliance-check", help="What to check: epoch|disks|fans|powers|raidgroups|partitions|fibrechannels|adapters|msdps|temperatures")
parser.add_argument("--enclosure-check", help="What to check: disks|fans|powers|temperatures")
parser.add_argument("--warning", type=int, help="Warning watermark")
parser.add_argument("--critical", type=int, help="Critical watermark")
args = parser.parse_args()

def Prep(filePath):
  try:
    with open (filePath,"r") as alertsFile:
      data=alertsFile.readlines()

    xmlDict = xmltodict.parse(str(data[0]))

  except Exception as error:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("UNKNOWN: " + str(error))
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=1, file=sys.stdout)
    sys.exit(3)
  return xmlDict

def GetTheComponentData(xmlDict,componentName,checks):
  """
  """
  base = xmlDict['monitorResponse']['computenode']['components']

  result = list()

  for components in base:
    if components['@name'] == componentName:
      for component in components['component']:
        if component in checks:
          result.append(components['component'][component])

  return result

def CheckDisks(baseobj):
  """
  """
  global returncode
  global outputSummary
  if len(baseobj) == 0:
    print("UNKNOWN: No data to parse for disks using the specified arguments")
    sys.exit(3)

  resultDict = dict()

  # Deconstruct the XML to a useable dictionary
  # For every entry in baseobj, ie every instance returned of the multiple disks.
  for disks in baseobj:

    # For every disk entry in disks
    for disk in disks['disk']:
      # For every property entry in disk
      tempDiskResultDict = dict()

      # Unpack the disk properties
      for prop in disk['property']:
        tempDiskResultDict[prop['@name']] = prop['@value']
      # Use the Slot Number and Enclosure ID to map back to this disk.
      slotNumber = tempDiskResultDict['Slot Number']
      enclosureId = tempDiskResultDict['Enclosure ID']

      # Add the key to the enclosure in case it is not already present
      if enclosureId not in resultDict:
        resultDict[enclosureId] = dict()
      # Store the data in a useable dictionary
      resultDict[enclosureId][slotNumber] = tempDiskResultDict

  # Iterate over the disks in the enclosures with some pretty output
  errorCount = 0
  for enclosure in resultDict:
    for disk in resultDict[enclosure]:
      tempOutput = "Disk '" + disk + "' with S/N '" + resultDict[enclosure][disk]['Serial Number'] + "' in enclosure '" + enclosure + "' is in the state '" + resultDict[enclosure][disk]['State'] + "' with a status of '" +resultDict[enclosure][disk]['Status'] + "'"
      if resultDict[enclosure][disk]["State"] != "OK" or int(resultDict[enclosure][disk]["ErrorStatus"]) != 0:
        criticalOutput.append(tempOutput)
        errorCount = errorCount + 1
        if returncode == 4 and returncode != 3:
          returncode = 2
      elif resultDict[enclosure][disk]["State"] == "OK" and int(resultDict[enclosure][disk]["ErrorStatus"]) == 0:
        output.append(tempOutput)
      else:
        returncode = 3
        unknownOutput.append(tempOutput)

  if returncode == 4:
    length = len(output)
    outputSummary = "All " + str(length) + " disks reported a state of OK"
  elif errorCount > 0:
    outputSummary = str(errorCount) + " disks with a non-OK state detected"

  return returncode

def CheckGeneric(baseobj,objtype):
  """
  """
  global returncode
  global outputSummary
  if len(baseobj) == 0:
    print("UNKNOWN: No data to parse for " + objtype + " using the specified arguments")
    sys.exit(3)

  resultDict = dict()
  description = None

  # Deconstruct the XML to a useable dictionary
  # For every entry in baseobj, ie every instance returned of the multiple fans.
  for objs in baseobj:

    if 'description' in objs:
      description = objs['description'] + " - "
    # For every disk entry in disks
    for obj in objs[objtype]:
      # For every property entry in objtype
      tempResultDict = dict()

      # Unpack the object properties
      # Exception for msdp
      if objtype == 'msdp' and not isinstance(obj, dict):
        obj = objs[objtype]

      for prop in obj['property']:
        tempResultDict[prop['@name']] = prop['@value']

      # Use the Name map back to this object.
      if objtype == 'fan' or objtype == 'raidgroup':
        objId = tempResultDict['Name']
      elif objtype == 'power' or objtype == 'fibrechannel' or objtype == 'msdp':
        objId = obj['@id']
      elif objtype == 'temperature':
        objId = tempResultDict['Type']
      elif objtype == 'adapter':
        objId = tempResultDict['Adapter model']
      elif objtype == 'partition':
        objId = tempResultDict['Partition']
      else:
        print("Unknown object type - good job!")
        sys.exit(3)

      # Store the data in a useable dictionary
      if objtype == 'temperature' and "Margin" in objId:
        continue
      resultDict[objId] = tempResultDict

  # Iterate over the objects with some pretty output
  errorCount = 0
  for obj in resultDict:
      if objtype == 'power' or objtype == 'fan' or objtype == 'msdp':
        tempOutput = str(objtype).title() + " '" + str(obj) + "' is in the state '" + resultDict[obj]['State'] + "' with a status of '" +resultDict[obj]['Status'] + "'"
      elif objtype == 'raidgroup':
        tempOutput = str(objtype).title() + " '" + obj + "' with a WWID of '" + resultDict[obj]['WWID'] + "' is in the state '" + resultDict[obj]['State'] + "' with a status of '" + resultDict[obj]['Status'] + "'"
      elif objtype == 'adapter':
        tempOutput = str(objtype).title() + " '" + obj + "' is in the state '" + resultDict[obj]['State'] + "' with an adapter status of '" + resultDict[obj]['Adapter Status'] + "'"
      elif objtype == 'fibrechannel':
        tempOutput = str(objtype).title() + " '" + str(obj) + "' with a WWN of '" + resultDict[obj]['Port WWN'] + "' is in the state '" + resultDict[obj]['State'] + "' with a status of '" + resultDict[obj]['Status'] + "'"
      elif objtype == 'partition':
        tempOutput = str(objtype).title() + " '" + str(obj) + "' with a usage of '" + str(resultDict[obj]['Used']) + "' is in the state '" + resultDict[obj]['State'] + "' with a status of '" +resultDict[obj]['Status'] + "'"
      elif objtype == 'temperature':
        tempOutput = str(objtype).title() + " '" + str(obj) + "' with a temperature of '" + str(resultDict[obj]['Temperature']) + "' is in the state '" + resultDict[obj]['State'] + "' with a status of '" +resultDict[obj]['Status'] + "'"

      if objtype == 'partition':
        if resultDict[obj]['Used'] != '-':
          perfdataList.append("'" + str(resultDict[obj]['Partition']) + "_used'=" + str(resultDict[obj]['Used']) + "")
      elif objtype == 'temperature':
        perfdataList.append("'" + str(obj) + "'=" + str(resultDict[obj]['Temperature']).split(" ")[0] + ";;;;")

      if resultDict[obj]["State"] != "OK" or int(resultDict[obj]["ErrorStatus"]) != 0:
        criticalOutput.append(tempOutput)
        errorCount = errorCount + 1
        if returncode == 4 and returncode != 3:
          returncode = 2
      elif resultDict[obj]["State"] == "OK" and int(resultDict[obj]["ErrorStatus"]) == 0:
        output.append(tempOutput)
      else:
        returncode = 3
        unknownOutput.append(tempOutput)

  if returncode == 4:
    length = len(output)
    if description:
      outputSummary = description + "All " + str(length) + " " + objtype + "s reported a state of OK"
    else:
      outputSummary = "All " + str(length) + " " + objtype + "s reported a state of OK"
  elif errorCount > 0:
    if description:
      outputSummary = description + str(errorCount) + " " + objtype + "s with a non-OK state detected"
    else:
      outputSummary = str(errorCount) + " " + objtype + "s with a non-OK state detected"

  return returncode

def CheckEpoch(xmlDict,epochSlackWarning,epochSlackCritical):
  """
  Check the reported epoch from the Alerts xml against the system time of the local server
  """
  global returncode
  global outputSummary
  epoch = int(xmlDict['monitorResponse']['computenode']['epoch'])

  now = datetime.now().timestamp()
  # Check if epoch is outside now-slack and now+slack.
  perfdataList.append("'epoch-delta'=" + str(now-epoch) + ";" + str(epochSlackWarning) + ";" + str(epochSlackCritical) + ";;")
  if not now-epochSlackCritical < epoch < now+epochSlackCritical:
    criticalOutput.append("Really old data, it is '" + str(int(now-epoch)) + "'s old")
    if returncode == 4:
      returncode = 2
  elif not now-epochSlackWarning < epoch < now+epochSlackWarning:
    warningOutput.append("Old data, it is '" + str(int(now-epoch)) + "'s old")
    if returncode == 4:
      returncode = 1
  else:
    outputSummary = "Epoch delta is within the specified slack, it is currently '" + str(int(now-epoch)) + "' seconds"

  return returncode


if __name__ == "__main__":
  # Prepare
  filePath = args.xmlfile
  xmlDict = Prep(filePath)

  # Do
  if args.appliance_check == "epoch":
    returncode = CheckEpoch(xmlDict,args.warning,args.critical)
  elif args.appliance_check == "disks":
    returncode = CheckDisks(GetTheComponentData(xmlDict,'appliance','disks'))
  elif args.enclosure_check == "disks":
    returncode = CheckDisks(GetTheComponentData(xmlDict,'enclosure','disks'))
  elif args.appliance_check == "raidgroups":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','raidgroups'),'raidgroup')
  elif args.appliance_check == "fans":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','fans'),'fan')
  elif args.enclosure_check == "fans":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'enclosure','fans'),'fan')
  elif args.appliance_check == "adapters":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','adapters'),'adapter')
  elif args.appliance_check == "powers":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','powers'),'power')
  elif args.enclosure_check == "powers":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'enclosure','powers'),'power')
  elif args.appliance_check == "partitions":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','partitions'),'partition')
  elif args.appliance_check == "fibrechannels":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','fibrechannels'),'fibrechannel')
  elif args.appliance_check == "msdps":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','msdps'),'msdp')
  elif args.appliance_check == "temperatures":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'appliance','temperatures'),'temperature')
  elif args.enclosure_check == "temperatures":
    returncode = CheckGeneric(GetTheComponentData(xmlDict,'enclosure','temperatures'),'temperature')
  
  else:
    if args.enclosure_check:
      print("UNKNOWN: Undefined --enclosure-check: " + str(args.enclosure_check))
    elif args.appliance_check:
      print("UNKNOWN: Undefined --appliance-check: " + str(args.appliance_check))
    else:
      print("UNKNOWN, read the code...")
    sys.exit(3)

  perfdata = " ".join(perfdataList)

  if returncode == 4:
    returncode = 0

  if returncode == 0:
    outputPrefix = "OK"
  elif returncode == 1:
    outputPrefix = "WARNING"
  elif returncode == 2:
    outputPrefix = "CRITICAL"
  elif returncode == 3:
    outputPrefix = "UNKNOWN"
   
  print(outputPrefix + ": " + outputSummary + " | " + str(perfdata))
  if len(unknownOutput) > 0:
    print("\n".join(unknownOutput))
  # Print critical output if any
  if len(criticalOutput) > 0:
    print("\n".join(criticalOutput))
  # Print warning output if any
  if len(warningOutput) > 0:
    print("\n".join(warningOutput))
  # Print normal output if any
  if len(output) > 0:
    print("\n".join(output))
  sys.exit(returncode)
