import json
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(HERE, 'token.json')

def get_tasks_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError('Token invalid and cannot be refreshed. Need re-auth.')
    return build('tasks', 'v1', credentials=creds, cache_discovery=False)

def main():
    service = get_tasks_service()
    tasklists = service.tasklists().list(maxResults=100).execute().get('items', [])
    all_data = []
    for tl in tasklists:
        tasks = []
        page_token = None
        while True:
            resp = service.tasks().list(
                tasklist=tl['id'],
                showCompleted=True,
                showHidden=True,
                maxResults=100,
                pageToken=page_token
            ).execute()
            tasks.extend(resp.get('items', []))
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
        all_data.append({
            'tasklist_id': tl['id'],
            'tasklist_title': tl['title'],
            'tasks': [
                {
                    'id': t.get('id'),
                    'title': t.get('title'),
                    'notes': t.get('notes', ''),
                    'status': t.get('status'),
                    'due': t.get('due', ''),
                    'parent': t.get('parent', ''),
                }
                for t in tasks
            ]
        })
    out_path = os.path.join(HERE, 'tasks_raw.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f'Wrote {out_path}')
    total = sum(len(tl['tasks']) for tl in all_data)
    print(f'Tasklists: {len(all_data)}, total tasks: {total}')

if __name__ == '__main__':
    main()
