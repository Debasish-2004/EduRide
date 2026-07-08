from locust import HttpUser, task, between

class StudentUser(HttpUser):
    wait_time = between(1, 3)

    @task(2)
    def home(self):
        self.client.get("/")

    @task(1)
    def student_dashboard(self):
        self.client.get("/student/")

    @task(5)
    def bus_locations(self):
        self.client.get("/student/api/bus-locations/")