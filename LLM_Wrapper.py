import requests

class LMStudioWrapper:
    def __init__(self):
        self.url = "http://localhost:1234/v1/chat/completions"
    def sendRequest(self, prompt):
        package = {"messages": [{"role": "user", "content": prompt}]}
        response = requests.post(self.url, json=package)
        if response.status_code == 200:
            print("Request successful!")
            # Print the response data
            print(response.json())
        return response.json()["choices"][0]["message"]["content"]


if __name__ == '__main__':
    wrapper = LMStudioWrapper()
    print(wrapper.sendRequest("What is the meaning of life?"))
