###############################################################
## test5.py                                                  ##
##
## 50 unit tests covering:
##   - Part I  (LLM)        : 10 tests
##   - Part II (Guardrails) : 30 tests
##   - Part III (Auberge)   : 10 tests
###############################################################

import requests
import unittest
import database

LLM = "http://localhost:3000/llm"
GUARDRAILS = "http://localhost:3001/guardrails"
AUBERGE = "http://localhost:3002/auberge"


def _strip(s: str) -> str:
    return (s or "").strip()


class Testing(unittest.TestCase):
    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _post_json(self, url, js, timeout=15):
        return requests.post(url, json=js, timeout=timeout)

    def _put_guardrail(self, gid, regx, sub, timeout=15, ok_status=(200, 201)):
        js = {"id": gid, "regx": regx, "sub": sub}
        rsp = requests.put(f"{GUARDRAILS}/{gid}", json=js, timeout=timeout)
        self.assertIn(rsp.status_code, ok_status)
        return rsp

    def _get_guardrail(self, gid, timeout=15):
        return requests.get(f"{GUARDRAILS}/{gid}", timeout=timeout)

    def _delete_guardrail(self, gid, timeout=15):
        return requests.delete(f"{GUARDRAILS}/{gid}", timeout=timeout)

    def _list_guardrails(self, timeout=15):
        return requests.get(GUARDRAILS, timeout=timeout)

    # ==========================================================
    # Part I: LLM (10 tests)
    # ==========================================================

    def test_001_llm_basic_fact(self):
        js = {"prompt": "What is the melting point of silver?"}
        rsp = self._post_json(LLM, js)

        self.assertEqual(rsp.status_code, 200)
        self.assertIn("output", rsp.json())
        self.assertTrue("961" in rsp.json()["output"])

    def test_002_llm_returns_output_string(self):
        js = {"prompt": "Say hello."}
        rsp = self._post_json(LLM, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", None)
        self.assertIsInstance(out, str)
        self.assertGreater(len(_strip(out)), 0)

    def test_003_llm_simple_math(self):
        js = {"prompt": "What is 2+2? Reply with only the digit."}
        rsp = self._post_json(LLM, js)

        self.assertEqual(rsp.status_code, 200)
        self.assertIn("4", _strip(rsp.json().get("output", "")))

    def test_004_llm_exact_string(self):
        js = {"prompt": "Reply with exactly: OK"}
        rsp = self._post_json(LLM, js)

        self.assertEqual(rsp.status_code, 200)
        self.assertIn("OK", rsp.json().get("output", ""))

    def test_005_llm_missing_prompt_field(self):
        rsp = self._post_json(LLM, {"x": "y"})
        self.assertIn(rsp.status_code, (400, 422))

    def test_006_llm_prompt_wrong_type_int(self):
        rsp = self._post_json(LLM, {"prompt": 123})
        self.assertIn(rsp.status_code, (400, 422))

    def test_007_llm_prompt_wrong_type_null(self):
        rsp = self._post_json(LLM, {"prompt": None})
        self.assertIn(rsp.status_code, (400, 422))

    def test_008_llm_empty_prompt(self):
        rsp = self._post_json(LLM, {"prompt": ""})
        # Accept either rejection (preferred) or a normal response.
        self.assertIn(rsp.status_code, (200, 400, 422))
        if rsp.status_code == 200:
            self.assertIsInstance(rsp.json().get("output", ""), str)

    def test_009_llm_wrong_method_get(self):
        rsp = requests.get(LLM, timeout=15)
        self.assertIn(rsp.status_code, (400, 404, 405))

    def test_010_llm_non_json_body(self):
        headers = {"Content-Type": "text/plain"}
        rsp = requests.post(LLM, data="hello", headers=headers, timeout=15)
        self.assertIn(rsp.status_code, (400, 415, 422))

    # ==========================================================
    # Part II: Guardrails (30 tests)
    # ==========================================================

    def test_011_guardrails_create_and_read_simple(self):
        database.db.clear()

        gid = "931"
        regx = r"Prince Andrew"
        sub = "Andrew Mountbatten-Windsor"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(gid, rsp.json()["id"])
        self.assertEqual(regx, rsp.json()["regx"])
        self.assertEqual(sub, rsp.json()["sub"])

    def test_012_guardrails_create_and_read_email(self):
        database.db.clear()

        gid = "email-001"
        regx = r"[a-zA-Z0-9_.]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+"
        sub = "<Email address>"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(gid, rsp.json()["id"])
        self.assertEqual(regx, rsp.json()["regx"])
        self.assertEqual(sub, rsp.json()["sub"])

    def test_013_guardrails_rejects_broken_regex(self):
        database.db.clear()

        gid = "Broken"
        regx = r"*a-z]"
        sub = "anything"
        js = {"id": gid, "regx": regx, "sub": sub}

        rsp = requests.put(f"{GUARDRAILS}/{gid}", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_014_guardrails_get_missing_returns_404(self):
        database.db.clear()
        rsp = self._get_guardrail("does-not-exist")
        self.assertIn(rsp.status_code, (404, 400))

    def test_015_guardrails_delete_missing_returns_404(self):
        database.db.clear()
        rsp = self._delete_guardrail("does-not-exist")
        self.assertIn(rsp.status_code, (404, 400))

    def test_016_guardrails_list_empty(self):
        database.db.clear()
        rsp = self._list_guardrails()
        self.assertEqual(rsp.status_code, 200)
        self.assertIsInstance(rsp.json(), list)
        self.assertEqual([], rsp.json())

    def test_017_guardrails_list_after_one_create(self):
        database.db.clear()
        self._put_guardrail("g1", r"Rome", "Roma", ok_status=(201,))

        rsp = self._list_guardrails()
        self.assertEqual(rsp.status_code, 200)
        self.assertIsInstance(rsp.json(), list)
        self.assertIn("g1", rsp.json())

    def test_018_guardrails_list_after_many_creates(self):
        database.db.clear()
        ids = ["g1", "g2", "g3"]
        self._put_guardrail("g1", r"a", "A", ok_status=(201,))
        self._put_guardrail("g2", r"b", "B", ok_status=(201,))
        self._put_guardrail("g3", r"c", "C", ok_status=(201,))

        rsp = self._list_guardrails()
        self.assertEqual(rsp.status_code, 200)
        self.assertCountEqual(ids, rsp.json())

    def test_019_guardrails_delete_existing_removes_from_list(self):
        database.db.clear()
        self._put_guardrail("g1", r"a", "A", ok_status=(201,))
        self._put_guardrail("g2", r"b", "B", ok_status=(201,))

        rsp = self._delete_guardrail("g1")
        self.assertIn(rsp.status_code, (200, 204))

        rsp = self._list_guardrails()
        self.assertEqual(rsp.status_code, 200)
        self.assertIn("g2", rsp.json())
        self.assertNotIn("g1", rsp.json())

    def test_020_guardrails_delete_then_get_404(self):
        database.db.clear()
        self._put_guardrail("g1", r"a", "A", ok_status=(201,))

        rsp = self._delete_guardrail("g1")
        self.assertIn(rsp.status_code, (200, 204))

        rsp = self._get_guardrail("g1")
        self.assertIn(rsp.status_code, (404, 400))

    def test_021_guardrails_overwrite_updates_value(self):
        database.db.clear()

        gid = "dup"
        self._put_guardrail(gid, r"cat", "CAT", ok_status=(201,))

        # Overwrite with new rule
        self._put_guardrail(gid, r"dog", "DOG", ok_status=(200, 201))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual("dup", rsp.json()["id"])
        self.assertEqual(r"dog", rsp.json()["regx"])
        self.assertEqual("DOG", rsp.json()["sub"])

    def test_022_guardrails_put_id_mismatch_rejected(self):
        database.db.clear()

        js = {"id": "B", "regx": r"x", "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_023_guardrails_put_missing_id_field(self):
        database.db.clear()

        js = {"regx": r"x", "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_024_guardrails_put_missing_regx_field(self):
        database.db.clear()

        js = {"id": "A", "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_025_guardrails_put_missing_sub_field(self):
        database.db.clear()

        js = {"id": "A", "regx": r"x"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_026_guardrails_put_id_wrong_type(self):
        database.db.clear()

        js = {"id": 123, "regx": r"x", "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/123", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_027_guardrails_put_regx_wrong_type(self):
        database.db.clear()

        js = {"id": "A", "regx": 123, "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_028_guardrails_put_sub_wrong_type(self):
        database.db.clear()

        js = {"id": "A", "regx": r"x", "sub": 123}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_029_guardrails_put_empty_regex_rejected(self):
        database.db.clear()

        js = {"id": "A", "regx": "", "sub": "y"}
        rsp = requests.put(f"{GUARDRAILS}/A", json=js, timeout=15)
        self.assertIn(rsp.status_code, (400, 422))

    def test_030_guardrails_empty_sub_allowed(self):
        database.db.clear()

        gid = "remove-word"
        regx = r"secret"
        sub = ""  # allow removing matches

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(sub, rsp.json()["sub"])

    def test_031_guardrails_stores_group_backreference(self):
        database.db.clear()

        gid = "pluralise"
        regx = r"(cat)"
        sub = r"\1s"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(regx, rsp.json()["regx"])
        self.assertEqual(sub, rsp.json()["sub"])

    def test_032_guardrails_stores_escaped_backslash(self):
        database.db.clear()

        gid = "path"
        regx = r"\\"  # a single backslash
        sub = r"/"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(regx, rsp.json()["regx"])
        self.assertEqual(sub, rsp.json()["sub"])

    def test_033_guardrails_list_is_json_list(self):
        database.db.clear()
        for i in range(5):
            self._put_guardrail(f"id{i}", r"x", "y", ok_status=(201,))

        rsp = self._list_guardrails()
        self.assertEqual(rsp.status_code, 200)
        self.assertIsInstance(rsp.json(), list)
        self.assertEqual(5, len(rsp.json()))

    def test_034_guardrails_create_id_with_dash_underscore(self):
        database.db.clear()

        gid = "a-b_c"
        regx = r"Rome"
        sub = "Roma"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(gid, rsp.json()["id"])

    def test_035_guardrails_create_numeric_id(self):
        database.db.clear()

        gid = "12345"
        regx = r"[0-9]+"
        sub = "<num>"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))
        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(gid, rsp.json()["id"])

    def test_036_guardrails_create_long_id(self):
        database.db.clear()

        gid = "x" * 80
        regx = r"foo"
        sub = "bar"

        self._put_guardrail(gid, regx, sub, ok_status=(201,))
        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(gid, rsp.json()["id"])

    def test_037_guardrails_put_non_json_body(self):
        database.db.clear()

        headers = {"Content-Type": "text/plain"}
        rsp = requests.put(f"{GUARDRAILS}/A", data="hello", headers=headers, timeout=15)
        self.assertIn(rsp.status_code, (400, 415, 422))

    def test_038_guardrails_wrong_method_post_not_allowed(self):
        database.db.clear()

        rsp = requests.post(GUARDRAILS, json={"id": "A", "regx": "x", "sub": "y"}, timeout=15)
        self.assertIn(rsp.status_code, (400, 404, 405))

    def test_039_guardrails_get_collection_wrong_method(self):
        database.db.clear()

        rsp = requests.delete(GUARDRAILS, timeout=15)
        self.assertIn(rsp.status_code, (400, 404, 405))

    def test_040_guardrails_get_returns_only_expected_fields(self):
        database.db.clear()

        gid = "fields"
        regx = r"foo"
        sub = "bar"
        self._put_guardrail(gid, regx, sub, ok_status=(201,))

        rsp = self._get_guardrail(gid)
        self.assertEqual(rsp.status_code, 200)
        self.assertCountEqual(["id", "regx", "sub"], list(rsp.json().keys()))

    # ==========================================================
    # Part III: Auberge (10 tests)
    # ==========================================================

    def test_041_auberge_no_guardrails_passthrough(self):
        database.db.clear()

        js = {"prompt": "Reply with exactly: banana"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        self.assertIn("banana", rsp.json().get("output", "").lower())

    def test_042_auberge_output_guardrail_applied(self):
        database.db.clear()

        # Replace output occurrences of banana
        self._put_guardrail("fruit", r"banana", "<fruit>", ok_status=(201,))

        js = {"prompt": "Reply with exactly: banana"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertIn("<fruit>", out)
        self.assertNotIn("banana", out.lower())

    def test_043_auberge_input_guardrail_changes_prompt(self):
        database.db.clear()

        # Change the prompt before it hits the LLM.
        self._put_guardrail("swap", r"banana", "apple", ok_status=(201,))

        js = {"prompt": "Reply with exactly: banana"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertIn("apple", out.lower())
        self.assertNotIn("banana", out.lower())

    def test_044_auberge_input_and_output_guardrails(self):
        database.db.clear()

        self._put_guardrail("in", r"banana", "apple", ok_status=(201,))
        self._put_guardrail("out", r"apple", "<fruit>", ok_status=(201,))

        js = {"prompt": "Reply with exactly: banana"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertIn("<fruit>", out)
        self.assertNotIn("banana", out.lower())
        self.assertNotIn("apple", out.lower())

    def test_045_auberge_multiple_guardrails_two_replacements(self):
        database.db.clear()

        self._put_guardrail("Roma", r"Rome", "Roma", ok_status=(201,))
        self._put_guardrail("Firenze", r"Florence", "Firenze", ok_status=(201,))

        js = {"prompt": "Reply with exactly: Rome Florence"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertIn("Roma", out)
        self.assertIn("Firenze", out)
        self.assertNotIn("Rome", out)
        self.assertNotIn("Florence", out)

    def test_046_auberge_replaces_all_occurrences(self):
        database.db.clear()

        self._put_guardrail("all", r"foo", "bar", ok_status=(201,))

        js = {"prompt": "Reply with exactly: foo foo foo"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertGreaterEqual(out.lower().count("bar"), 3)
        self.assertNotIn("foo", out.lower())

    def test_047_auberge_regex_digits(self):
        database.db.clear()

        self._put_guardrail("nums", r"\\d+", "<num>", ok_status=(201,))

        js = {"prompt": "Reply with exactly: 123 456"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertGreaterEqual(out.count("<num>"), 2)

    def test_048_auberge_empty_sub_removes_word(self):
        database.db.clear()

        self._put_guardrail("rm", r"secret", "", ok_status=(201,))

        js = {"prompt": "Reply with exactly: secret"}
        rsp = self._post_json(AUBERGE, js)

        self.assertEqual(rsp.status_code, 200)
        out = rsp.json().get("output", "")
        self.assertNotIn("secret", out.lower())

    def test_049_auberge_missing_prompt_field(self):
        database.db.clear()

        rsp = self._post_json(AUBERGE, {"x": "y"})
        self.assertIn(rsp.status_code, (400, 422))

    def test_050_auberge_prompt_wrong_type(self):
        database.db.clear()

        rsp = self._post_json(AUBERGE, {"prompt": 123})
        self.assertIn(rsp.status_code, (400, 422))


if __name__ == "__main__":
    unittest.main(verbosity=2)
