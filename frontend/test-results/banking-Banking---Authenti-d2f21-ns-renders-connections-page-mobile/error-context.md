# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - generic [ref=e3]:
      - img [ref=e4]
      - generic [ref=e6]: Authentication required. Provide Bearer token (JWT or service token).
    - button [ref=e7] [cursor=pointer]:
      - img [ref=e8]
  - generic [ref=e12]:
    - img [ref=e14]
    - generic [ref=e17]:
      - heading "Access denied" [level=2] [ref=e18]
      - paragraph [ref=e19]: You don't have permission to view this page.
    - generic [ref=e20]:
      - link "Go home" [ref=e21]:
        - /url: /
      - link "Sign in" [ref=e22]:
        - /url: /auth/login
  - region "Notifications (F8)":
    - list
  - alert [ref=e23]
```