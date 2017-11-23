#!/usr/bin/python
from firebase import firebase

def main():
	f = firebase.FirebaseApplication('https://testing-27640.firebaseio.com/',
	 authentication=None)
	for i in range(50,300):
		f.post('/messages', {'message' : 'Test ' + str(i)})

main()
