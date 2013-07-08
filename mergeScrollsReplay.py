import json
from sys import exit, stdout, argv

file1 = None
file2 = None
outfilestream = stdout
if len(argv) == 3:
    file1 = argv[1]
    file2 = argv[2]
elif len(argv) == 4:
    file1 = argv[1]
    file2 = argv[2]
    outfilestream = open(argv[3], "w")
else:
    print("Usage: {0} In-File1 InFile2 [OutFile]".format(argv[0]))
    exit(1)


watchAs = "black"


def readNextJsonMessage(handle, assertMsg=None):
    """
    Decode the first non-empty line from handle as json.
    If assertMsg is given raise an Error if the msg-attribute did not match or no Message was found.
    """
    s = "\n"
    while(s == "\n"):
        s = handle.readline()
        if s == "":
            if assertMsg is not None:
                raise "EOF instead of {0}".format(assertMsg)
            return None
    message = json.loads(s)
    if assertMsg is not None and message['msg'] != assertMsg:
        raise "{0} instead of {1}".format(message['msg'], assertMsg)
    return message


def writeMessage(message):
    outfilestream.write(json.dumps(message))
    outfilestream.write("\n\n\n")


def isTurnBeginOrEndGame(message):
    if message['msg'] == 'NewEffects':
        if len(message['effects']) == 1:
            if "TurnBegin" in message['effects'][0] or "EndGame" in message['effects'][0]:
                return True
    return False


def isTurnBegin(message):
    if message['msg'] == 'NewEffects':
        if len(message['effects']) == 1:
            if "TurnBegin" in message['effects'][0]:
                return True
    return False


def isEndGame(message):
    if message['msg'] == 'NewEffects':
        if len(message['effects']) == 1:
            if "EndGame" in message['effects'][0]:
                return True
    return False

with open(file1, "r") as file1handle:
    with open(file2, "r") as file2handle:
        m1 = readNextJsonMessage(file1handle, "ServerInfo")
        m2 = readNextJsonMessage(file2handle, "ServerInfo")

        writeMessage(m1)  # TODO Decide which message to keep

        if m1['version'] != m2['version']:  # version differs
            print("Replay versions differ {0} vs {1}!".format(m1['version'], m2['version']))
            exit(1)

        m1 = readNextJsonMessage(file1handle, "GameInfo")
        m2 = readNextJsonMessage(file2handle, "GameInfo")

        #We now got 2 GameInfo-Messages. Check if they are from the same match
        if m1['gameId'] != m2['gameId']:
            print("GameId differs: {0} vs {1}".format(m1['gameId'], m2['gameId']))
            exit(1)

        whiteHandle = None
        whiteMessage = None
        blackHandle = None
        blackMessage = None
        if m1['color'] == 'white' and m2['color'] == 'black':
            whiteHandle = file1handle
            whiteMessage = m1
            blackHandle = file2handle
            blackMessage = m2
        elif m1['color'] == 'black' and m2['color'] == 'white':
            blackHandle = file1handle
            blackMessage = m1
            whiteHandle = file2handle
            whiteMessage = m2
        else:
            print("Colors do not match")
            exit(1)
        del m1, m2

        #Getting ProfileIds
        profileIds = {
            "white": whiteMessage["whiteAvatar"]['profileId'],
            "black": whiteMessage["blackAvatar"]['profileId'],
        }
        watchAsProfileId = profileIds[watchAs]
        #TODO Check if Player-Names match

        #Also writing any other GameInfo-Messages from player white
        while whiteMessage['msg'] == "GameInfo":
            writeMessage(whiteMessage)  # TODO Decide which message to keep
            whiteMessage = readNextJsonMessage(file1handle)
            if whiteMessage is None:
                print("Replay ended prematurely")
                exit(5)
        while blackMessage['msg'] == "GameInfo":
            blackMessage = readNextJsonMessage(file2handle)
            if blackMessage is None:
                print("Replay ended prematurely")
                exit(1)

        if whiteMessage['msg'] != "ActiveResources" or blackMessage['msg'] != "ActiveResources":
            print("Coudn't read ActiveRessources")
            exit(1)

        whiteRessourcesMessage = whiteMessage  # Save the ActiveResouces-Message for later
        blackRessourcesMessage = blackMessage
        whiteMessage = readNextJsonMessage(whiteHandle, "NewEffects")
        blackMessage = readNextJsonMessage(blackHandle, "NewEffects")
        #TODO check for TurnBegin

        while True:
            #assert: whiteMessage and blackMessage contains the TurnBegin or Endgame Message for this Turn
            #TurnBegin-Message is not yet written!
            if isEndGame(whiteMessage):
                #Game has ended
                writeMessage(whiteMessage)
                break

            currentColor = whiteMessage['effects'][0]['TurnBegin']['color']

            stream = None
            if currentColor == "white":
                writeMessage(whiteRessourcesMessage)
                stream = whiteHandle
            elif currentColor == "black":
                writeMessage(blackRessourcesMessage)
                stream = blackHandle
            message = whiteMessage  # black and white are equal.

            #Only Relay Messages for the active player, cause he sees more
            while True:
                if message['msg'] == "NewEffects":
                    for effect in message['effects']:
                        if "HandUpdate" in effect:
                            if effect['HandUpdate']['profileId'] == profileIds[currentColor]:
                                effect['HandUpdate']['profileId'] = watchAsProfileId
                writeMessage(message)
                message = readNextJsonMessage(stream)

                if message is None:
                    print("Replay does not has a valid end")
                    exit(1)

                #Check if we have the EndTurn-Message
                if isTurnBeginOrEndGame(message):
                    #The turn of the current player is over now.
                    #Writing last Message back
                    otherStream = None
                    if currentColor == "white":
                        whiteMessage = message
                        otherStream = blackHandle
                    elif currentColor == "black":
                        blackMessage = message
                        otherStream = whiteHandle
                    #Skip all messages on the other player
                    message = readNextJsonMessage(otherStream)
                    while True:  # Successfully nested 3 Infinte loops
                        if message is None:
                            print("Replay does not has a valid end2")
                            exit(1)
                        if isTurnBeginOrEndGame(message):
                            break
                        message = readNextJsonMessage(otherStream)
                    #Writing beck the OtherPlayer-Message
                    if currentColor == "white":
                        blackMessage = message
                    elif currentColor == "black":
                        whiteMessage = message
                    break
