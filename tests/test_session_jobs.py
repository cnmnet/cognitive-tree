import threading
import unittest

from harness.session_jobs import JobManager


class TestJobManager(unittest.TestCase):
    def setUp(self):
        self.manager = JobManager()

    def test_create_and_update_job(self):
        job_id = self.manager.create("chat")
        self.assertIn(job_id, self.manager.jobs)
        self.assertEqual(self.manager.jobs[job_id]["status"], "queued")
        self.manager.set(job_id, progress=50, status="running")
        self.assertEqual(self.manager.jobs[job_id]["progress"], 50)
        self.manager.log(job_id, "开始处理", "system")
        self.assertEqual(len(self.manager.jobs[job_id]["logs"]), 1)

    def test_run_job_success(self):
        job_id = self.manager.create("batch")
        self.manager.run(job_id, lambda: {"ok": True})
        job = self.manager.jobs[job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["progress"], 100)
        self.assertEqual(job["result"], {"ok": True})

    def test_run_job_failure_records_error(self):
        job_id = self.manager.create("deep-reasoning")

        def fail():
            raise RuntimeError("boom")

        self.manager.run(job_id, fail)
        job = self.manager.jobs[job_id]
        self.assertEqual(job["status"], "error")
        self.assertIn("boom", job["error"])
        self.assertTrue(any("任务失败" in item["message"] for item in job["logs"]))

    def test_stop_flag_is_managed(self):
        job_id = self.manager.create("daily-plan")
        self.manager.stop_flags[job_id] = threading.Event()
        self.assertIn(job_id, self.manager.stop_flags)
        self.manager.stop_flags[job_id].set()
        self.assertTrue(self.manager.stop_flags[job_id].is_set())


if __name__ == "__main__":
    unittest.main()
