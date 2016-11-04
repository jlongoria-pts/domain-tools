from xml.dom.minidom import parseString
import requests
import cherrypy
import json
import os

### Constants and configuration.

#cherrypy
sockethost = '127.0.0.1'
socketport = 8081

#requests
baseUrl   = 'ux-dev.ptsteams.local/jasperserver-pro'
authUser = 'jasperadmin'
authPass = 'jasperadmin'


### Dictionaries and word-banks.

translations = {
    "DT": "Date",
    "INVOL": "Involuntary",
    "TERM": "Termination",
    "RESIGN": "Resignation",
    "CRIM": "Criminal",
    "HIST": "History",
    "SUB": "Substitute",
    "TS": "Timestamp",
    "MOD": "Modified"
}

stopwords = [
    "TEAMS"
]

acronyms = [
    "PEIMS",
    "DAEP",
    "JJAEP",
    "PCN",
    "ID",
    "DOB"
]


### Server-interaction methods.

def getDomainProperties():

    url = "http://<baseUrl>/rest_v2/resources/"
    url = url.replace("<baseUrl>", baseUrl)

    parameters = {
      "type":"semanticLayerDataSource"
    }

    headers = {
      "accept": "application/json"
    }

    response = requests.get(
      url,
      headers=headers,
      params=parameters,
      auth=(authUser, authPass)
    )

    domains = response.json()

    return domains['resourceLookup']

def getDomainSchema(path):
    domainPath = path + "_files"

    #GET schema.xml file for selected domain.
    url = 'http://<baseUrl>/rest_v2/resources/<domainPath>/schema.xml'

    url = url.replace("<baseUrl>", baseUrl)
    url = url.replace("/<domainPath>", domainPath)

    response = requests.get(
      url,
      auth=(authUser,authPass)
    )

    return response.text


### Unique token-finding methods

def getUniqueTokens(schema):
    uniqueTokens = []
    tokenContext = []

    for item in schema.getElementsByTagName("item"):
        label = item.getAttribute("label")

        label = label.replace("__", " ")
        label = label.replace("_", " ")
        label = label.strip()

        tokenizedLabel = label.split(" ")

        for token in tokenizedLabel:
            if token not in uniqueTokens:
                uniqueTokens.append(token)
                tokenContext.append(label)

    return {"context": tokenContext, "tokens": uniqueTokens}

### Translation and formatting methods.

def removeStopwords(label):
    newLabel = ""
    tokenizedLabel = label.split(" ")

    for token in tokenizedLabel:
        if token in stopwords:
            tokenizedLabel.remove(token)

    newLabel = " ".join(tokenizedLabel)

    return newLabel

def translateLabel(label):
    newLabel = []
    tokenizedLabel = label.split(" ")

    for token in tokenizedLabel:
        if token in translations.keys():
            newLabel.append(translations[token])
        else:
            newLabel.append(token)

    return ( " ".join(newLabel) )

def formatLabel(label):
    newLabel = []
    tokenizedLabel = label.split(" ")

    for token in tokenizedLabel:
        formattedToken = token

        if token not in acronyms:
            formattedToken = token[0].upper() + token[1:].lower()

        newLabel.append( formattedToken )

    return ( " ".join(newLabel) )


### XML-tree modifying methods.

def modifyNodeLabel(label):
    label = label.replace("__", " ")
    label = label.replace("_", " ")
    label = label.strip()

    label = removeStopwords(label)
    label = translateLabel(label)
    label = formatLabel(label)

    return label

def modifyColumnNodes(schema):
    for item in schema.getElementsByTagName("item"):
        label = item.getAttribute("label")

        label = modifyNodeLabel(label)

        item.setAttribute("label", label)

def modifyTableNodes(schema):
    for itemGroup in schema.getElementsByTagName("itemGroup"):
        label = itemGroup.getAttribute("label")

        label = modifyNodeLabel(label)

        itemGroup.setAttribute("label", label)


### Page-rendering methods.

class Root(object):

    @cherrypy.expose
    def index(self):

        #Array of domain-properties objects.
        domains = getDomainProperties()

        #Generates list of links using domains array.
        listOfDomains = ""

        for domain in domains:
            label, uri = domain["label"], domain["uri"]

            params = "domainLabel=" + label + "&domainUri=" + uri

            listOfDomains += (
                "<tr><td>"
                  "<a href='schemaEditor?" +params+ "'>" +label+ "</a>"
                "</td></tr>\n"
            )

        #Inserts the list of links into an HTML document.
        page = (
            open("index.html", "r")
              .read()
              .replace("<!--List of Domains-->", listOfDomains)
        )

        return page


    @cherrypy.expose
    def schemaEditor(self, domainLabel, domainUri):

        xmlDoc = getDomainSchema(domainUri)
        schema = parseString(xmlDoc).documentElement

        uniqueTokens = getUniqueTokens(schema)
        #modifyColumnNodes(schema)

        #newXmlDoc = schema.toprettyxml(newl='')
        #open("schema.xml", "w").write(newXmlDoc)

        forms = ""
        for i in range( 0, len(uniqueTokens["tokens"]) ):
            label = uniqueTokens["context"][i]
            value = uniqueTokens["tokens"][i]

            forms += (
              "<tr><td>" +label+ "</td>"+
              "<td><input id="+value+" value="+value+">"+
              "</input></td></tr>"
            )

        page = (
            open("schemaEditor.html", "r")
                .read()
                .replace("<!--List of Unique Tokens-->", forms)
        )

        return page


    @cherrypy.expose
    @cherrypy.tools.json_in()
    def submit(self):
        domainPath = cherrypy.session.get('domainPath')
        schemaText = cherrypy.session.get('schemaText')
        schema     = cherrypy.request.json['schema']


        #Generated by PostMan. Overwrites the existing domain schema file.
        url = "http://"+baseUrl+"/rest_v2/resources"+domainPath+"/schema.xml"
        querystring = {"overwrite":"true"}
        headers = {
            'accept': "application/json",
            'content-type': "application/repository.schema+xml",
            'content-disposition': "attachment; filename=schema.xml"
        }

        #Send the request to JasperServer's REST API.
        response = requests.request("PUT", url,
                                    data=payload,
                                    headers=headers,
                                    params=querystring,
                                    auth=(authUser, authPass))

        return response.text


#Server upstart and configuration.
if __name__ == '__main__':
    conf = {
	        '/': {
	            'tools.sessions.on': True,
				'tools.staticdir.root': os.getcwd(),
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/html'],
                'tools.sessions.timeout': 3600
                #timeout measured in minutes
		},
            '/static': {
             'tools.staticdir.on': True,
             'tools.staticdir.dir': '',
             'tools.gzip.on': True,
             'tools.gzip.mime_types': ['text/javascript','text/css']
        }
	}
    cherrypy.config.update({'server.socket_host': sockethost,
                            'server.socket_port': socketport,})
    cherrypy.quickstart(Root(), '/', conf)
