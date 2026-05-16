from locust import HttpUser, task, between
import random

class StatsUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def post_data(self):
        device = f"sensor{random.randint(1, 10)}"
        payload = {"x": random.uniform(0,100), "y": random.uniform(0,100), "z": random.uniform(0,100)}
        self.client.post(f"/data/{device}", json=payload)

    @task(1)
    def request_analysis(self):
        device = f"sensor{random.randint(1, 10)}"
        resp = self.client.post(f"/analysis/device/{device}", json={})
        if resp.status_code == 200:
            task_id = resp.json()["task_id"]
            self.client.get(f"/analysis/result/{task_id}", name="/analysis/result")
