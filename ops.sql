-- Small, made-up ops database for the text-to-SQL demo. Times are UTC, ISO 8601.

CREATE TABLE services (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    team  TEXT NOT NULL,
    tier  INTEGER NOT NULL CHECK (tier IN (1, 2, 3))  -- 1 = most critical
);

CREATE TABLE deploys (
    id           INTEGER PRIMARY KEY,
    service_id   INTEGER NOT NULL REFERENCES services (id),
    version      TEXT NOT NULL,
    deployed_at  TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'rolled_back'))
);

CREATE TABLE incidents (
    id           INTEGER PRIMARY KEY,
    service_id   INTEGER NOT NULL REFERENCES services (id),
    title        TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('sev1', 'sev2', 'sev3')),  -- sev1 = worst
    started_at   TEXT NOT NULL,
    resolved_at  TEXT  -- NULL while the incident is still open
);

CREATE TABLE costs (
    service_id  INTEGER NOT NULL REFERENCES services (id),
    month       TEXT NOT NULL,  -- 'YYYY-MM'
    usd         REAL NOT NULL,
    PRIMARY KEY (service_id, month)
);

INSERT INTO services (id, name, team, tier) VALUES
    (1, 'checkout',      'payments',  1),
    (2, 'payments-api',  'payments',  1),
    (3, 'search',        'discovery', 2),
    (4, 'auth',          'platform',  1),
    (5, 'notifications', 'growth',    3),
    (6, 'reporting',     'data',      3);

INSERT INTO deploys (service_id, version, deployed_at, status) VALUES
    (1, 'v2.14.0', '2026-09-03T10:12:00Z', 'succeeded'),
    (1, 'v2.15.0', '2026-09-24T14:40:00Z', 'failed'),
    (1, 'v2.15.1', '2026-09-24T16:05:00Z', 'succeeded'),
    (1, 'v2.16.0', '2026-10-15T09:30:00Z', 'succeeded'),
    (1, 'v2.17.0', '2026-11-10T11:00:00Z', 'rolled_back'),
    (2, 'v5.2.0',  '2026-09-08T08:20:00Z', 'succeeded'),
    (2, 'v5.3.0',  '2026-10-02T13:15:00Z', 'succeeded'),
    (2, 'v5.4.0',  '2026-10-29T15:45:00Z', 'failed'),
    (2, 'v5.4.1',  '2026-10-30T09:10:00Z', 'succeeded'),
    (3, 'v1.8.0',  '2026-09-12T12:00:00Z', 'succeeded'),
    (3, 'v1.9.0',  '2026-10-07T10:30:00Z', 'rolled_back'),
    (3, 'v1.9.1',  '2026-10-08T09:00:00Z', 'succeeded'),
    (3, 'v1.10.0', '2026-11-04T14:20:00Z', 'succeeded'),
    (4, 'v3.0.0',  '2026-09-16T07:45:00Z', 'succeeded'),
    (4, 'v3.1.0',  '2026-10-21T08:00:00Z', 'succeeded'),
    (4, 'v3.2.0',  '2026-11-12T07:30:00Z', 'failed'),
    (5, 'v0.9.0',  '2026-09-19T16:00:00Z', 'succeeded'),
    (5, 'v0.10.0', '2026-10-24T17:10:00Z', 'succeeded'),
    (6, 'v4.4.0',  '2026-09-29T11:25:00Z', 'succeeded'),
    (6, 'v4.5.0',  '2026-11-06T10:50:00Z', 'succeeded');

INSERT INTO incidents (service_id, title, severity, started_at, resolved_at) VALUES
    (1, 'Checkout errors after v2.15.0',        'sev1', '2026-09-24T14:52:00Z', '2026-09-24T16:10:00Z'),
    (1, 'Slow cart page during sale',           'sev2', '2026-10-18T19:00:00Z', '2026-10-18T21:30:00Z'),
    (1, 'Payment button missing on Safari',     'sev2', '2026-11-10T11:20:00Z', '2026-11-10T12:05:00Z'),
    (2, 'Card provider timeouts',               'sev1', '2026-10-05T03:10:00Z', '2026-10-05T05:40:00Z'),
    (2, 'Duplicate refunds after v5.4.0',       'sev1', '2026-10-29T16:00:00Z', '2026-10-30T09:30:00Z'),
    (3, 'Search results empty for some users',  'sev2', '2026-10-07T10:45:00Z', '2026-10-08T09:15:00Z'),
    (3, 'High packet drop on search nodes',     'sev3', '2026-11-02T08:00:00Z', '2026-11-02T10:00:00Z'),
    (4, 'Login failures for SSO users',         'sev1', '2026-11-12T07:40:00Z', '2026-11-12T09:00:00Z'),
    (4, 'Token refresh latency spike',          'sev3', '2026-09-30T13:00:00Z', '2026-09-30T13:45:00Z'),
    (5, 'Push notifications delayed',           'sev3', '2026-10-26T18:00:00Z', NULL),
    (6, 'Nightly report job failing',           'sev3', '2026-11-14T02:00:00Z', NULL),
    (2, 'Webhook queue growing',                'sev2', '2026-11-16T22:30:00Z', NULL);

INSERT INTO costs (service_id, month, usd) VALUES
    (1, '2026-09', 4200.00), (1, '2026-10', 4650.00), (1, '2026-11', 4800.00),
    (2, '2026-09', 3900.00), (2, '2026-10', 4100.00), (2, '2026-11', 4300.00),
    (3, '2026-09', 2600.00), (3, '2026-10', 3100.00), (3, '2026-11', 2900.00),
    (4, '2026-09', 1800.00), (4, '2026-10', 1850.00), (4, '2026-11', 1900.00),
    (5, '2026-09',  700.00), (5, '2026-10',  950.00), (5, '2026-11',  820.00),
    (6, '2026-09', 1200.00), (6, '2026-10', 1250.00), (6, '2026-11', 2400.00);
