# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e4]:
    - img [ref=e6]
    - generic [ref=e9]:
      - heading "Access denied" [level=2] [ref=e10]
      - paragraph [ref=e11]: You don't have permission to view this page.
    - generic [ref=e12]:
      - link "Go home" [ref=e13] [cursor=pointer]:
        - /url: /
      - link "Sign in" [ref=e14] [cursor=pointer]:
        - /url: /auth/login
  - region "Notifications (F8)":
    - list
  - alert [ref=e15]
```