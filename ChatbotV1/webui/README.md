# Web User Interface

Python is the number one programming language used for machine learning, while Java is still the most popular language for web development. The purpose of this web UI is to demonstrate how to deploy a neural network model created and trained in Python and TensorFlow into a Java environment. A SOAP-based web service is generated to meet this need. The steps to create the running environment in a Windows system are described below. Similar procedures can be followed in Linux, but have not been tried.

The description below assumes that you are configuring DNS entry Hugochat.net to point to your machine, and running the web service server and client on the same one. In order to make the DNS entry Hugochat.net work, edit the hosts file (located at C:\Windows\System32\drivers\etc in a normal installation) and add the following line:
    
    127.0.0.1  		Hugochat.net

## Python Server

Tornado web server (version 4.5.1) and Tornado-webservices (for SOAP web services: https://github.com/rancavil/tornado-webservices) are employed to create the web service server. The Tornado web server is installed while the source code of the Tornado-webservices package is included (Do not install the Tornado-webservices package, because file: webservices.py, was modified to allow a parameter to be passed into the web service.)

```bash
pip install tornado
```

When tornado web server is installed, run the commands below to bring up the web service. 

```bash
cd webui
cd server
python chatservice.py
```

Now, you should be able to see the WDSL file here: http://Hugochat.net:8080/ChatService?wsdl (or http://localhost:8080/ChatService?wsdl).

## Java Client

The Java client is tested with Java 1.7 and Tomcat 7.0. You can try later versions if you prefer. Following the steps below to prepare the client:

1. Install Java 1.7.
2. Install Tomcat 7.0. Choose port 80 (at least not port 8080 if you are running the python web service on the same machine, which is on port 8080).
3. Copy the whole folder chatClient to C drive as C:\chatClient. 
4. Make changes to the server.xml of the Tomcat installation to add the chatClient web application (copy the Host portion for chatClient into server.xml). You need to change the name of the host if you are using a different domain.
6. Change the service address in C:\chatClient\ROOT\ajax\getChatReply.jsp in case you are using a different domain.
7. Restart Tomcat.

And now you are ready to try it: http://Hugochat.net, if you are using this domain.
