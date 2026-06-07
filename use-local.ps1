# Create use-local.ps1
echo 'API_BASE = "http://127.0.0.1:8000"' > use-local.txt
## --------------Write-Host "Switched to LOCAL"-----------

(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "http://127.0.0.1:8000"' | Set-Content D:\research_agent\streamlit_app.py; 

##--------------- "SWitched to lambda"------------
(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com"' | Set-Content D:\research_agent\streamlit_app.py