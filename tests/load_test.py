from locust import HttpUser, task, between

class DiligencePipelineUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def test_validate_gateway(self):
        payload = {
            "thesis": "A micro-SaaS tool assisting freelance copywriters with automated contracts.",
            "niche": "copywriter contract platforms",
            "monetization": "usage_based",
            "constraints": "solo dev, $500 marketing budget",
            "known_competitors": ["Bonsai", "DocuSign", "HelloSign"]
        }
        
        # Test endpoint latency
        with self.client.post("/validate", json=payload, catch_response=True) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"Expected status 202, got {response.status_code}")
