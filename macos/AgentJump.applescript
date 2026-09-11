on open location theURL
	set pythonBin to "/usr/bin/python3"
	set jumpScript to "AGENT_JUMP_PY"
	do shell script pythonBin & " " & quoted form of jumpScript & " " & quoted form of theURL & " >> /tmp/agentjump.log 2>&1"
end open location

on run
	display notification "Click a bastion agent:// link in the browser to connect." with title "AgentJump"
end run
