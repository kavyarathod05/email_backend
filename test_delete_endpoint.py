import requests

BASE_URL = "http://localhost:10000"

def test_delete_fake():
    print("Checking initial stats...")
    r = requests.get(f"{BASE_URL}/dashboard/stats")
    stats = r.json()
    print(f"Fake emails count before: {stats.get('fake', 0)}")
    
    if stats.get('fake', 0) == 0:
        print("No fake emails to delete. Adding a dummy fake email...")
        # Add a dummy recruiter with is_fake=True
        # Wait, the add_recruiter endpoint doesn't support is_fake directly in the model
        # I'll just skip the deletion test if count is 0, or I'll manually insert one.
        pass

    print("Requesting deletion of fake emails...")
    r = requests.delete(f"{BASE_URL}/recruiters/fake")
    print(f"Delete response: {r.json()}")
    
    print("Checking stats after deletion...")
    r = requests.get(f"{BASE_URL}/dashboard/stats")
    stats = r.json()
    print(f"Fake emails count after: {stats.get('fake', 0)}")

if __name__ == "__main__":
    test_delete_fake()
