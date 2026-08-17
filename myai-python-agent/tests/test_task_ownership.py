import unittest

from app.task.runtime import TaskRunStore
from app.task.service.task_service import TaskService


class TaskOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.run_store = TaskRunStore()
        self.service = TaskService(
            rec_planner=object(),
            task_executor=object(),
            stats=object(),
            run_store=self.run_store,
        )
        self.run = self.run_store.create(user_id="owner", content="private task")
        self.run_store.mark_queued(self.run, background=True)

    def tearDown(self):
        self.service.background_executor.shutdown(wait=False, cancel_futures=True)

    def test_get_run_only_returns_owner_run(self):
        self.assertIsNotNone(self.service.get_run(self.run.task_run_id, user_id="owner"))
        self.assertIsNone(self.service.get_run(self.run.task_run_id, user_id="intruder"))

    def test_non_owner_cannot_request_cancellation(self):
        result = self.service.request_cancel(self.run.task_run_id, user_id="intruder")

        self.assertIsNone(result)
        self.assertFalse(self.run.cancel_requested)


if __name__ == "__main__":
    unittest.main()
