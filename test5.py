###############################################################
## test5.py                                                  ## 
###############################################################
import requests
import unittest
import database

LLM = "http://localhost:3000/llm"
GUARDRAILS = "http://localhost:3001/guardrails"
AUBERGE = "http://localhost:3002/auberge"

class Testing(unittest.TestCase):
  ############################################################
  ## test_001_llm				            ##
  ############################################################
  def test_001_llm(self):
    js  = {"prompt":"What is the melting point of silver?"}
    rsp = requests.post(LLM,json=js)

    self.assertEqual(rsp.status_code,200)
    self.assertTrue("961" in rsp.json()["output"])

  ############################################################
  ## test_002_guardrails				    ##
  ############################################################
  def test_002_guardrails(self):
    database.db.clear()

    id   = "931"
    regx = r"Prince Andrew"
    sub  = "Andrew Mountbatten-Windsor"
    js   = {"id":id,"regx":regx,"sub":sub}

    rsp = requests.put(f'{GUARDRAILS}/{id}',json=js)
    self.assertEqual(rsp.status_code,201)

    rsp = requests.get(f'{GUARDRAILS}/{id}')
    self.assertEqual(rsp.status_code,200)
    self.assertEqual(id,rsp.json()["id"])
    self.assertEqual(regx,rsp.json()["regx"])
    self.assertEqual(sub,rsp.json()["sub"])

  ############################################################
  ## test_003_guardrails				    ##
  ############################################################
  def test_003_guardrails(self):
    database.db.clear()

    id   = "email-001"
    regx = r"[a-zA-Z0-9_.]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+" 
    sub  = "<Email address>"
    js   = {"id":id,"regx":regx,"sub":sub}

    rsp = requests.put(f'{GUARDRAILS}/{id}',json=js)
    self.assertEqual(rsp.status_code,201)

    rsp = requests.get(f'{GUARDRAILS}/{id}')
    self.assertEqual(rsp.status_code,200)
    self.assertEqual(id,rsp.json()["id"])
    self.assertEqual(regx,rsp.json()["regx"])
    self.assertEqual(sub,rsp.json()["sub"])

  ############################################################
  ## test_004_guardrails				    ##
  ############################################################
  def test_004_guardrails(self):
    database.db.clear()

    id   = "Broken"
    regx = r"*a-z]" 
    sub  = "anything"
    js   = {"id":id,"regx":regx,"sub":sub}

    rsp = requests.put(f'{GUARDRAILS}/{id}',json=js)
    self.assertEqual(rsp.status_code,400) # Bad input

  ############################################################
  ## test_005_auberge                                       ##
  ############################################################
  def test_005_auberge(self):
    database.db.clear()

    id   = "Roma"
    regx = r"Rome" 
    sub  = "Roma"
    js   = {"id":id,"regx":regx,"sub":sub}

    rsp = requests.put(f'{GUARDRAILS}/{id}',json=js)
    self.assertEqual(rsp.status_code,201) # Created 

    id2   = "Firenze"
    regx2 = r"Florence" 
    sub2  = "Firenze"
    js2   = {"id":id2,"regx":regx2,"sub":sub2}

    rsp = requests.put(f'{GUARDRAILS}/{id2}',json=js2)
    self.assertEqual(rsp.status_code,201) # Created 

    js3 = {"prompt":"What are the major cities of Italy?"}
    rsp = requests.post(AUBERGE,json=js3)
    self.assertEqual(rsp.status_code,200)
    self.assertTrue("Roma" in rsp.json()["output"])
    self.assertTrue("Firenze" in rsp.json()["output"])
