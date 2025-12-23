# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e4]:
    - img [ref=e6]
    - heading "404" [level=1] [ref=e9]
    - heading "Page not found" [level=2] [ref=e10]
    - paragraph [ref=e11]: The page you're looking for doesn't exist or has been moved.
    - generic [ref=e12]:
      - link "Dashboard" [ref=e13] [cursor=pointer]:
        - /url: /
        - img [ref=e14]
        - text: Dashboard
      - button "Go back" [ref=e17] [cursor=pointer]:
        - img [ref=e18]
        - text: Go back
  - region "Notifications (F8)":
    - list
  - alert [ref=e20]
```