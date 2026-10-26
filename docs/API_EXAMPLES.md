# API examples (run `python server.py` first)

```bash
B=http://localhost:8000
```

## List with filters and paging
```bash
curl "$B/api/internships?status=open&work_mode=remote&page=1&limit=5"
curl "$B/api/internships?q=brightwave"
```
→ `200` `{"data":[…],"meta":{"page":1,"limit":5,"total":2,"total_pages":1}}`

## Detail
```bash
curl $B/api/internships/1
```
→ `200` `{"data":{"id":1,"title":"Frontend Developer Intern", …}}`

## Create
```bash
curl -i -X POST $B/api/internships -H 'Content-Type: application/json' -d '{
  "title":"DevOps Intern","company":"Orbit AI","location":"Remote",
  "work_mode":"remote","duration_weeks":10,"stipend_monthly":16000}'
```
→ `201 Created`, header `Location: /api/internships/9`, body `{"data":{"id":9, …, "status":"open"}}`

## Update
```bash
# partial
curl -X PATCH $B/api/internships/9 -H 'Content-Type: application/json' -d '{"status":"closed"}'
# full replace (all required fields)
curl -X PUT $B/api/internships/9 -H 'Content-Type: application/json' -d '{
  "title":"DevOps Intern","company":"Orbit AI","location":"Remote","work_mode":"remote","duration_weeks":12}'
```
→ `200` with the updated record; `updated_at` changes.

## Delete
```bash
curl -i -X DELETE $B/api/internships/9
```
→ `204 No Content` (repeat it → `404`)

## Errors
```bash
curl -X POST $B/api/internships -H 'Content-Type: application/json' -d '{"title":"x","work_mode":"moon"}'
```
→ `422`
```json
{"error":{"code":"VALIDATION_ERROR","message":"Request body failed validation","details":[
  {"field":"company","message":"is required"},
  {"field":"location","message":"is required"},
  {"field":"duration_weeks","message":"is required"},
  {"field":"title","message":"must be a string of 3-120 characters"},
  {"field":"work_mode","message":"must be one of: remote, hybrid, onsite"}]}}
```
```bash
curl -i $B/api/internships/999     # 404 NOT_FOUND
curl -i $B/api/internships/abc     # 400 INVALID_ID
curl -i -X POST $B/api/internships -H 'Content-Type: application/json' -d '{bad'   # 400 INVALID_JSON
curl -i -X POST $B/api/internships -d 'hi'     # 415 UNSUPPORTED_MEDIA_TYPE
curl -i -X PUT $B/api/internships              # 405 METHOD_NOT_ALLOWED
# 409 CONFLICT: POST the same title + company twice
```
