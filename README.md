# Greystone Code Challenge

## Getting Started

Open a terminal in a folder and run the following commands:

```
git clone https://github.com/SangusIT/greystone-code-challenge.git
cd greystone-code-challenge
python -m venv venv # or python3 -m venv venv depending on your install
source venv/bin/activate # use this command for Mac/Linux, source venv/Scripts/activate for Windows if you are using Git Bash, otherwise \venv\Scripts\activate
pip install -r requirements.txt
fastapi dev app.py
```

You should now see this when you go to http://127.0.0.1:8000/docs in a browser:

![Image](https://github.com/user-attachments/assets/5c6f6f8d-5645-42b0-808e-2e5356a8df05)

## Notes

- OAuth2 Authentication Required
- Uses SQLite database
- Users can only share loans they have created or had shared with them
- Set up a workflow to run pytest when new pull requests are created

In order to create, share and query loans through the browser documentation page you will first need to create a user and "Log In" by clicking "Authorize" and filling out the username and password fields on this form:

![Image](https://github.com/user-attachments/assets/4cf92a58-67de-4169-8337-7b5c6bbc5966)