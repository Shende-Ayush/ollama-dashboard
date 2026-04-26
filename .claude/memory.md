# SYSTEM MEMORY

## KNOWN ISSUES

### Docker restart loop
- Cause: port conflict
- Fix: change exposed port in docker-compose

---

## SUCCESSFUL FIXES

### Ollama not responding
- Restarted service
- Verified port 11434 active

---

## RULES LEARNED

- Always check port usage before starting services
- Restart is not a fix without root cause

---

## FIXES

Docker restart loop
- Cause: port already in use
- Fix: change port mapping

---

## RULES

- Always check logs before restarting services