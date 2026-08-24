from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "gate.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_frontend_delivery_gate", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


class VerifyFrontendDeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_git("init")
        self.run_git("config", "user.email", "gate@example.com")
        self.run_git("config", "user.name", "Gate Test")
        (self.repo / "prd.md").write_text("# Product\n", encoding="utf-8")
        (self.repo / "app.tsx").write_text(
            "export const value = 1;\n", encoding="utf-8"
        )
        self.run_git("add", "prd.md", "app.tsx")
        self.run_git("commit", "-m", "initial")
        self.head = self.run_git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self):
        self.temporary.cleanup()

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def make_contract(
        self,
        risk: str = "R0",
        requested: list[str] | None = None,
        confirmed: list[str] | None = None,
    ) -> dict[str, object]:
        issue_set = requested or ["TEST-1"]
        args = Namespace(
            repo=str(self.repo),
            base=self.head,
            head=None,
            risk=risk,
            issue=issue_set,
            source=[gate.SourceSpec("PRD", "PRD", "business", "prd.md")],
            run_root=str(self.root / "runs"),
            run_id="test-run",
        )
        contract, _ = gate.contract_payload(args)
        contract["traceability"]["confirmed_issue_set"] = confirmed or issue_set
        product = contract["product_contract"]
        product["user_visible_change"] = "Verify the visible behavior"
        product["authority_map"] = [{"dimension": "business", "source_id": "PRD"}]
        product["acceptance_scenarios"] = [
            {"id": "SCN-1", "expected": "Behavior remains visible"}
        ]
        if risk in {"R2", "R3", "R4"}:
            product["lifecycle_matrix"] = [
                {"from": "draft", "action": "save", "to": "persisted"}
            ]
        contract["state"] = "FROZEN"
        contract["approval"] = {
            "status": "APPROVED",
            "approved_by": "user",
            "approved_at": gate.utc_now(),
        }
        contract["contract_fingerprint"] = gate.contract_fingerprint(contract)
        return contract

    def passing_results(self, contract: dict[str, object]) -> dict[str, object]:
        results = {
            "run_id": contract["run_id"],
            "auditor": {"id": "fresh-auditor", "independent_context": True},
            "issue_set": contract["traceability"]["confirmed_issue_set"],
            "gates": [],
            "warnings": [],
            "unverified_items": [],
        }
        for gate_id in gate.required_gates(str(contract["risk_level"])):
            results["gates"].append(
                {
                    "id": gate_id,
                    "status": "PASS",
                    "evidence_level": gate.GATE_MIN_EVIDENCE[gate_id],
                    "summary": f"{gate_id} passed",
                    "artifacts": [],
                    "unverified": [],
                }
            )
        return results

    def test_r4_includes_all_lower_risk_gates(self):
        gates = gate.required_gates("R4")
        self.assertEqual(gates[:3], ["L0_SOURCE", "L1_IMPACT", "L2_STATIC"])
        self.assertIn("L6_REAL_BACKEND", gates)
        self.assertEqual(gates[-1], "L8_INDEPENDENT_REVIEW")

    def test_contract_rejects_missing_source_and_issue_mismatch(self):
        contract = self.make_contract(requested=["TEST-1"], confirmed=["TEST-2"])
        contract["source_manifest"][0]["exists"] = False
        errors = gate.validate_contract(contract, for_verify=True)
        self.assertTrue(any("SOURCE_MISSING" in error for error in errors))
        self.assertTrue(any("ISSUE_SET_MISMATCH" in error for error in errors))

    def test_r2_contract_requires_lifecycle_matrix(self):
        contract = self.make_contract("R2")
        contract["product_contract"]["lifecycle_matrix"] = []
        contract["contract_fingerprint"] = gate.contract_fingerprint(contract)
        errors = gate.validate_contract(contract, for_verify=True)
        self.assertTrue(any("lifecycle_matrix" in error for error in errors))

    def test_unresolved_p1_source_conflict_blocks_freeze(self):
        contract = self.make_contract()
        contract["product_contract"]["conflicts"] = [
            {"id": "CONFLICT-1", "priority": "P1", "status": "OPEN"}
        ]
        errors = gate.validate_contract(contract, for_freeze=True)
        self.assertTrue(any("SOURCE_CONFLICT" in error for error in errors))

    def test_source_drift_is_detected(self):
        contract = self.make_contract()
        (self.repo / "prd.md").write_text("# Changed Product\n", encoding="utf-8")
        drift = gate.source_drift(contract)
        self.assertEqual(drift[0]["id"], "PRD")
        self.assertIn("sha256", drift[0]["changed_fields"])

    def test_historical_snapshot_ignores_current_worktree(self):
        (self.repo / "app.tsx").write_text(
            "export const value = 2;\n", encoding="utf-8"
        )
        self.run_git("add", "app.tsx")
        self.run_git("commit", "-m", "historical head")
        historical_head = self.run_git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "app.tsx").write_text(
            "export const value = 3;\n", encoding="utf-8"
        )

        snapshot = gate.repository_snapshot(self.repo, self.head, historical_head)

        self.assertEqual(snapshot["target_kind"], "GIT_REF")
        self.assertEqual(snapshot["head"], historical_head)
        self.assertFalse(snapshot["dirty"])
        self.assertEqual(snapshot["status_lines"], [])
        self.assertEqual(snapshot["changed_files"], ["M\tapp.tsx"])

    def test_live_repository_drift_blocks_stale_report(self):
        contract = self.make_contract()
        (self.repo / "app.tsx").write_text(
            "export const value = 2;\n", encoding="utf-8"
        )

        report = gate.finalize_report(contract, self.passing_results(contract))

        self.assertEqual(report["final_status"], "BLOCKED")
        self.assertTrue(
            any(
                reason.startswith("REPOSITORY_CHANGED:")
                for reason in report["blocking_reasons"]
            )
        )
        self.assertTrue(report["repository_drift"])

    def test_historical_contract_remains_stable_after_worktree_changes(self):
        (self.repo / "app.tsx").write_text(
            "export const value = 2;\n", encoding="utf-8"
        )
        self.run_git("add", "app.tsx")
        self.run_git("commit", "-m", "historical target")
        historical_head = self.run_git("rev-parse", "HEAD").stdout.strip()
        args = Namespace(
            repo=str(self.repo),
            base=self.head,
            head=historical_head,
            risk="R0",
            issue=["TEST-1"],
            source=[gate.SourceSpec("PRD", "PRD", "business", "prd.md")],
            run_root=str(self.root / "runs"),
            run_id="historical-run",
        )
        contract, _ = gate.contract_payload(args)
        contract["product_contract"]["user_visible_change"] = "Historical behavior"
        contract["product_contract"]["authority_map"] = [
            {"dimension": "business", "source_id": "PRD"}
        ]
        contract["product_contract"]["acceptance_scenarios"] = [
            {"id": "SCN-1", "expected": "Historical behavior remains visible"}
        ]
        contract["state"] = "FROZEN"
        contract["approval"] = {
            "status": "APPROVED",
            "approved_by": "user",
            "approved_at": gate.utc_now(),
        }
        contract["contract_fingerprint"] = gate.contract_fingerprint(contract)
        (self.repo / "app.tsx").write_text(
            "export const value = 3;\n", encoding="utf-8"
        )

        report = gate.finalize_report(contract, self.passing_results(contract))

        self.assertEqual(report["final_status"], "PASS")
        self.assertEqual(report["repository_drift"], [])

    def test_baseline_delta_fails_only_on_new_findings(self):
        baseline = {
            "findings": [
                {"tool": "typecheck", "file": "old.ts", "line": 1, "message": "old"}
            ]
        }
        current = {
            "findings": [
                {"tool": "typecheck", "file": "old.ts", "line": 1, "message": "old"},
                {"tool": "typecheck", "file": "new.ts", "line": 2, "message": "new"},
            ]
        }
        delta = gate.compare_findings(baseline, current)
        self.assertEqual(delta["status"], "FAIL")
        self.assertEqual(delta["counts"]["new"], 1)
        self.assertEqual(delta["counts"]["unchanged"], 1)

    def test_fully_evidenced_r0_passes(self):
        contract = self.make_contract()
        report = gate.finalize_report(contract, self.passing_results(contract))
        self.assertEqual(report["final_status"], "PASS")
        self.assertEqual(report["blocking_reasons"], [])

    def test_independent_auditor_is_mandatory(self):
        contract = self.make_contract()
        results = self.passing_results(contract)
        results["auditor"]["independent_context"] = False
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "BLOCKED")
        self.assertIn("INDEPENDENT_AUDITOR_UNAVAILABLE", report["blocking_reasons"])

    def test_insufficient_evidence_blocks_required_gate(self):
        contract = self.make_contract("R1")
        results = self.passing_results(contract)
        browser = next(item for item in results["gates"] if item["id"] == "L5_BROWSER")
        browser["evidence_level"] = "UNIT_VERIFIED"
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "BLOCKED")
        self.assertTrue(
            any(
                "INSUFFICIENT_EVIDENCE: L5_BROWSER" in item
                for item in report["blocking_reasons"]
            )
        )

    def test_required_gate_failure_cannot_pass(self):
        contract = self.make_contract()
        results = self.passing_results(contract)
        results["gates"][1]["status"] = "FAIL"
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "FAIL")
        self.assertIn("REQUIRED_GATE_FAILED: L1_IMPACT", report["blocking_reasons"])

    def test_proven_failure_takes_precedence_over_incomplete_environment_gate(self):
        contract = self.make_contract("R1")
        results = self.passing_results(contract)
        impact = next(item for item in results["gates"] if item["id"] == "L1_IMPACT")
        impact["status"] = "FAIL"
        visual = next(item for item in results["gates"] if item["id"] == "L7_VISUAL")
        visual["status"] = "BLOCKED_BY_ENVIRONMENT"
        visual.pop("evidence_level")

        report = gate.finalize_report(contract, results)

        self.assertEqual(report["final_status"], "FAIL")
        self.assertIn(
            "REQUIRED_GATE_BLOCKED_BY_ENVIRONMENT: L7_VISUAL",
            report["blocking_reasons"],
        )
        self.assertIn("REQUIRED_GATE_FAILED: L1_IMPACT", report["blocking_reasons"])

    def test_source_drift_still_blocks_even_when_a_gate_fails(self):
        contract = self.make_contract()
        (self.repo / "prd.md").write_text("# Changed Product\n", encoding="utf-8")
        results = self.passing_results(contract)
        results["gates"][1]["status"] = "FAIL"

        report = gate.finalize_report(contract, results)

        self.assertEqual(report["final_status"], "BLOCKED")
        self.assertTrue(
            any(
                reason.startswith("SOURCE_CHANGED:")
                for reason in report["blocking_reasons"]
            )
        )

    def test_unapproved_baseline_waiver_blocks(self):
        contract = self.make_contract()
        results = self.passing_results(contract)
        results["gates"][2]["status"] = "WAIVED_BASELINE"
        results["gates"][2].pop("evidence_level")
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "BLOCKED")
        self.assertIn("UNAPPROVED_WAIVER: L2_STATIC", report["blocking_reasons"])

    def test_approved_scoped_unexpired_waiver_is_accepted(self):
        contract = self.make_contract()
        contract["waivers"] = [
            {
                "gate_id": "L2_STATIC",
                "status": "APPROVED",
                "approved_by": "user",
                "issue_set": ["TEST-1"],
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            }
        ]
        contract["contract_fingerprint"] = gate.contract_fingerprint(contract)
        results = self.passing_results(contract)
        results["gates"][2]["status"] = "WAIVED_BASELINE"
        results["gates"][2].pop("evidence_level")
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "PASS")

    def test_p2_warning_produces_pass_with_warnings(self):
        contract = self.make_contract()
        results = self.passing_results(contract)
        results["warnings"] = [{"priority": "P2", "message": "minor pixel drift"}]
        report = gate.finalize_report(contract, results)
        self.assertEqual(report["final_status"], "PASS_WITH_P2_WARNINGS")

    def test_markdown_is_rendered_from_report_status(self):
        contract = self.make_contract()
        report = gate.finalize_report(contract, self.passing_results(contract))
        markdown = gate.render_markdown(report)
        self.assertIn("Final status: `PASS`", markdown)
        self.assertIn("`L0_SOURCE`", markdown)

    def test_freeze_requires_separate_output_path(self):
        contract = self.make_contract()
        contract["state"] = "DRAFT"
        contract["approval"] = {
            "status": "PENDING",
            "approved_by": None,
            "approved_at": None,
        }
        contract.pop("contract_fingerprint")
        contract_path = self.root / "draft.json"
        gate.write_json(contract_path, contract)
        args = Namespace(
            contract=str(contract_path),
            output=str(contract_path),
            approved_by="user",
            late_reconstruction=False,
        )
        with self.assertRaisesRegex(gate.GateError, "独立输出路径"):
            gate.command_freeze(args)


if __name__ == "__main__":
    unittest.main()
