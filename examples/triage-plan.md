# Tech Debt Triage Plan
**Repo:** /Users/shuchita/projects/my-flutter-app
**Scanned:** 2026-05-30T10:42:18Z
**Total markers found:** 47

## Summary
| Priority | Count |
|----------|-------|
| High     | 8     |
| Medium   | 19    |
| Low      | 20    |

**Scoring formula:** `score = log(age_days+1)/log(731) × 0.6 + min(file_mods/50,1) × 0.4`
High > 0.6 · Medium > 0.3 · Low ≤ 0.3

---

## High Priority

### 1. `lib/auth/token_service.dart:87` - FIXME
- **Text:** `FIXME: refresh token not retried on 401 - users get silently logged out`
- **Author:** shuchita@example.com
- **Age:** 418 days
- **File activity:** 34 modifications
- **Score:** 0.84
- **Fingerprint:** `a3f92c1d4b7e`

### 2. `lib/data/feed_repository.dart:203` - HACK
- **Text:** `HACK: pagination hardcoded to 20, backend contract says max 50`
- **Author:** dev@example.com
- **Age:** 521 days
- **File activity:** 28 modifications
- **Score:** 0.81
- **Fingerprint:** `b1c04d9a2f3e`

### 3. `lib/sync/conflict_resolver.dart:45` - FIXME
- **Text:** `FIXME: last-write-wins - concurrent edits from two devices silently drop one`
- **Author:** shuchita@example.com
- **Age:** 389 days
- **File activity:** 41 modifications
- **Score:** 0.80
- **Fingerprint:** `c9e31f7b0a12`

### 4. `lib/cache/image_cache.dart:118` - TODO
- **Text:** `TODO: eviction policy missing - cache grows unbounded on low-memory devices`
- **Author:** shuchita@example.com
- **Age:** 302 days
- **File activity:** 22 modifications
- **Score:** 0.72
- **Fingerprint:** `d4a87c2e1b56`

### 5. `lib/notifications/push_handler.dart:67` - FIXME
- **Text:** `FIXME: deep link parsing breaks when notification arrives while app is killed`
- **Author:** dev@example.com
- **Age:** 271 days
- **File activity:** 19 modifications
- **Score:** 0.68
- **Fingerprint:** `e7b23d9f0c41`

### 6. `lib/db/migrations/v2_schema.dart:12` - HACK
- **Text:** `HACK: skipping migration validation to ship before deadline - revisit`
- **Author:** shuchita@example.com
- **Age:** 244 days
- **File activity:** 17 modifications
- **Score:** 0.65
- **Fingerprint:** `f2c14a8e3d07`

### 7. `lib/auth/biometric_guard.dart:33` - TODO
- **Text:** `TODO: fallback to PIN not implemented - biometric failure = locked out`
- **Author:** dev@example.com
- **Age:** 198 days
- **File activity:** 24 modifications
- **Score:** 0.62
- **Fingerprint:** `g8d05b7f1e29`

### 8. `lib/analytics/event_batcher.dart:99` - FIXME
- **Text:** `FIXME: batch flush not called on app backgrounding - events lost`
- **Author:** shuchita@example.com
- **Age:** 183 days
- **File activity:** 21 modifications
- **Score:** 0.61
- **Fingerprint:** `h5e91c3a2f48`

---

## Medium Priority

### 9. `lib/ui/home_screen.dart:312` - TODO
- **Text:** `TODO: shimmer loading state missing - blank screen for 300ms on slow networks`
- **Author:** dev@example.com
- **Age:** 156 days
- **File activity:** 18 modifications
- **Score:** 0.57
- **Fingerprint:** `i3f72d0b4c15`

### 10. `lib/models/user_profile.dart:58` - TEMP
- **Text:** `TEMP: hardcoded avatar URL until CDN migration completes`
- **Author:** shuchita@example.com
- **Age:** 201 days
- **File activity:** 8 modifications
- **Score:** 0.49
- **Fingerprint:** `j6a43e9c1d82`

*...9 more medium priority items in full report...*
