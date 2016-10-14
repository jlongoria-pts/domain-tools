from xml.dom.minidom import parseString
import requests
import cherrypy
import json
import os

#cherrypy
sockethost = '127.0.0.1'
socketport = 8081

#requests
baseUrl   = 'ux-dev.ptsteams.local/jasperserver-pro'
authUser = 'jasperadmin'
authPass = 'jasperadmin'

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

### Server-interaction methods

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

        labels = []
        for item in schema.getElementsByTagName("item"):
            label = item.getAttribute("label")

            label = label.replace("__", " ")
            label = label.replace("_", " ")
            label = label.strip()

            label = removeStopwords(label)
            label = translateLabel(label)
            label = formatLabel(label)

            labels.append(label + "<br>")

            item.setAttribute("label", label)

        newXmlDoc = schema.toprettyxml(newl='')

        open("schema.xml", "w").write(newXmlDoc)

        return open("schema.xml", "r").read()


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