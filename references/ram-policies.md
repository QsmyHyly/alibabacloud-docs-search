# RAM Policies for Documentation Search

This skill uses the Information Query Service (IQS) for programmatic documentation search. The following permissions are required if using API-based search (web search works without credentials).

## Required Permissions

| Permission | Purpose |
|-----------|---------|
| `iqs:UnifiedSearch` | Search documentation content |
| `iqs:ReadPageBasic` | Extract content from documentation pages |

## RAM Policy JSON

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iqs:UnifiedSearch",
        "iqs:ReadPageBasic"
      ],
      "Resource": "*"
    }
  ]
}
```

## Credential Configuration

This skill uses the Alibaba Cloud default credential chain:

1. **Environment Variables** (highest priority):
   - `ALIBABA_CLOUD_ACCESS_KEY_ID`
   - `ALIBABA_CLOUD_ACCESS_KEY_SECRET`

2. **CLI Config File**: `~/.aliyun/config.json`

3. **No credentials**: Web-based search still works without any credentials

> Note: For basic documentation search and retrieval, no credentials are needed. The web scraping method works without any API access.
