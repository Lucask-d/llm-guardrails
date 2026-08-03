###############################################################
## test6.py                                                  ## 
###############################################################
import requests
import unittest
import database

LLM = "http://localhost:3000/llm"
GUARDRAILS = "http://localhost:3001/guardrails"
AUBERGE = "http://localhost:3002/auberge"

class TestingMore(unittest.TestCase):
  ############################################################
  ## test_006_llm_basic_nonempty                              ##
  ############################################################
  def test_006_llm_basic_nonempty(self):
    js  = {"prompt":"Say the word hello."}
    rsp = requests.post(LLM,json=js)

    self.assertEqual(rsp.status_code,200)
    self.assertTrue("output" in rsp.json())
    self.assertTrue(isinstance(rsp.json()["output"], str))
    self.assertTrue(len(rsp.json()["output"].strip()) > 0)

  ############################################################
  ## test_007_llm_missing_prompt                              ##
  ############################################################
  def test_007_llm_missing_prompt(self):
    rsp = requests.post(LLM,json={})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_008_llm_prompt_not_string                           ##
  ############################################################
  def test_008_llm_prompt_not_string(self):
    rsp = requests.post(LLM,json={"prompt":123})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_009_llm_wrong_method                                ##
  ############################################################
  def test_009_llm_wrong_method(self):
    rsp = requests.get(LLM)
    # Many implementations return 405 Method Not Allowed, some 404.
    self.assertIn(rsp.status_code,[404,405])

  ############################################################
  ## test_010_guardrails_list_empty                           ##
  ############################################################
  def test_010_guardrails_list_empty(self):
    database.db.clear()

    rsp = requests.get(GUARDRAILS)
    self.assertEqual(rsp.status_code,200)
    self.assertTrue(isinstance(rsp.json(), list))
    self.assertEqual(len(rsp.json()),0)

  ############################################################
  ## test_011_guardrails_list_multiple                         ##
  ############################################################
  def test_011_guardrails_list_multiple(self):
    database.db.clear()

    items = [
      ("g1", r"Rome", "Roma"),
      ("g2", r"Florence", "Firenze"),
      ("g3", r"London", "Londinium"),
    ]

    for (id,regx,sub) in items:
      js = {"id":id,"regx":regx,"sub":sub}
      rsp = requests.put(f"{GUARDRAILS}/{id}", json=js)
      self.assertEqual(rsp.status_code,201)

    rsp = requests.get(GUARDRAILS)
    self.assertEqual(rsp.status_code,200)
    ids = rsp.json()

    self.assertTrue(isinstance(ids, list))
    self.assertEqual(set(ids), set([x[0] for x in items]))

  ############################################################
  ## test_012_guardrails_get_missing                           ##
  ############################################################
  def test_012_guardrails_get_missing(self):
    database.db.clear()

    rsp = requests.get(f"{GUARDRAILS}/does-not-exist")
    self.assertIn(rsp.status_code,[404,410])

  ############################################################
  ## test_013_guardrails_delete_then_get                       ##
  ############################################################
  def test_013_guardrails_delete_then_get(self):
    database.db.clear()

    id   = "todelete"
    regx = r"Secret"
    sub  = "<Redacted>"
    js   = {"id":id,"regx":regx,"sub":sub}

    rsp = requests.put(f"{GUARDRAILS}/{id}", json=js)
    self.assertEqual(rsp.status_code,201)

    rsp = requests.delete(f"{GUARDRAILS}/{id}")
    self.assertIn(rsp.status_code,[200,204])

    rsp = requests.get(f"{GUARDRAILS}/{id}")
    self.assertIn(rsp.status_code,[404,410])

  ############################################################
  ## test_014_guardrails_delete_missing                         ##
  ############################################################
  def test_014_guardrails_delete_missing(self):
    database.db.clear()

    rsp = requests.delete(f"{GUARDRAILS}/nope")
    # Some services treat deleting missing as 404, some as 200/204.
    self.assertIn(rsp.status_code,[200,204,404,410])

  ############################################################
  ## test_015_guardrails_put_id_mismatch                        ##
  ############################################################
  def test_015_guardrails_put_id_mismatch(self):
    database.db.clear()

    url_id  = "abc"
    body_id = "xyz"
    js = {"id":body_id,"regx":r"Rome","sub":"Roma"}

    rsp = requests.put(f"{GUARDRAILS}/{url_id}", json=js)
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_016_guardrails_put_missing_fields                     ##
  ############################################################
  def test_016_guardrails_put_missing_fields(self):
    database.db.clear()

    id = "missing-fields"

    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"sub":"x"})
    self.assertEqual(rsp.status_code,400)

    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":r"x"})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_017_guardrails_put_non_string_fields                  ##
  ############################################################
  def test_017_guardrails_put_non_string_fields(self):
    database.db.clear()

    id = "bad-types"
    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":["x"],"sub":"y"})
    self.assertEqual(rsp.status_code,400)

    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":r"x","sub":123})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_018_guardrails_update_overwrite                       ##
  ############################################################
  def test_018_guardrails_update_overwrite(self):
    database.db.clear()

    id   = "update-me"
    regx = r"Rome"

    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":regx,"sub":"Roma"})
    self.assertEqual(rsp.status_code,201)

    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":regx,"sub":"ROMA"})
    # Depending on your implementation this may be 200 or 201.
    self.assertIn(rsp.status_code,[200,201])

    rsp = requests.get(f"{GUARDRAILS}/{id}")
    self.assertEqual(rsp.status_code,200)
    self.assertEqual(id, rsp.json()["id"])
    self.assertEqual(regx, rsp.json()["regx"])
    self.assertEqual("ROMA", rsp.json()["sub"])

  ############################################################
  ## test_019_auberge_basic_nonempty                            ##
  ############################################################
  def test_019_auberge_basic_nonempty(self):
    database.db.clear()

    js  = {"prompt":"Say hello."}
    rsp = requests.post(AUBERGE, json=js)

    self.assertEqual(rsp.status_code,200)
    self.assertTrue("output" in rsp.json())
    self.assertTrue(isinstance(rsp.json()["output"], str))
    self.assertTrue(len(rsp.json()["output"].strip()) > 0)

  ############################################################
  ## test_020_auberge_output_sanitised_deterministic            ##
  ############################################################
  def test_020_auberge_output_sanitised_deterministic(self):
    database.db.clear()

    # This guardrail will replace the entire output with a known string
    # (assuming sanitisation uses Python re.sub).
    id   = "all-output"
    regx = r".*"
    sub  = "SANITISED"
    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":regx,"sub":sub})
    self.assertEqual(rsp.status_code,201)

    rsp = requests.post(AUBERGE, json={"prompt":"Tell me anything."})
    self.assertEqual(rsp.status_code,200)
    self.assertEqual("SANITISED", rsp.json()["output"].strip())

  ############################################################
  ## test_021_auberge_missing_prompt                            ##
  ############################################################
  def test_021_auberge_missing_prompt(self):
    database.db.clear()

    rsp = requests.post(AUBERGE, json={})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_022_auberge_prompt_not_string                         ##
  ############################################################
  def test_022_auberge_prompt_not_string(self):
    database.db.clear()

    rsp = requests.post(AUBERGE, json={"prompt":False})
    self.assertEqual(rsp.status_code,400)

  ############################################################
  ## test_023_auberge_email_like_redaction                       ##
  ############################################################
  def test_023_auberge_email_like_redaction(self):
    database.db.clear()

    # Make it very likely the model will include '@' if it follows instructions.
    # Then ensure output guardrails remove it.
    id   = "at-sign"
    regx = r"@"
    sub  = "[at]"
    rsp = requests.put(f"{GUARDRAILS}/{id}", json={"id":id,"regx":regx,"sub":sub})
    self.assertEqual(rsp.status_code,201)

    rsp = requests.post(AUBERGE, json={"prompt":"Output exactly this email: a@b.com"})
    self.assertEqual(rsp.status_code,200)
    out = rsp.json()["output"]

    self.assertTrue("[at]" in out)
    self.assertTrue("@" not in out)

  ############################################################
  ## test_024_auberge_multiple_guardrails_apply                  ##
  ############################################################
  def test_024_auberge_multiple_guardrails_apply(self):
    database.db.clear()

    # Replace two different tokens if they appear in the output.
    rsp = requests.put(f"{GUARDRAILS}/g-rome", json={"id":"g-rome","regx":r"Rome","sub":"Roma"})
    self.assertEqual(rsp.status_code,201)

    rsp = requests.put(f"{GUARDRAILS}/g-florence", json={"id":"g-florence","regx":r"Florence","sub":"Firenze"})
    self.assertEqual(rsp.status_code,201)

    rsp = requests.post(AUBERGE, json={"prompt":"Mention Rome and Florence in your answer."})
    self.assertEqual(rsp.status_code,200)

    out = rsp.json()["output"]
    self.assertTrue("Roma" in out)
    self.assertTrue("Firenze" in out)
