## F-09 — Public API Tests

This is not merely a matter of folder naming.

The testing must demonstrate that the Public API functions as a stable interface, rather than just a superficial one.

I propose the following structure:

```
tests/
├── core/
├── public_api/
│   ├── core/
│   │   ├── test_stage_api.py
│   │   ├── test_step_api.py
│   │   ├── test_spu_api.py
│   │   └── test_results_api.py
│   └── integrations/
│       └── prefect/
│           ├── test_stage_api.py
│           ├── test_step_api.py
│           └── test_result_mapping_api.py
├── integrations/
│   └── prefect/
└── architecture/
```

Key tests should include:

- Importing the Core API without Prefect.
- Importing the Prefect API with Prefect.
- Ensuring internal modules are not exposed as public contracts.
- Prohibiting wildcard exports.
- Verifying that every public contract has a clearly defined owner.
- Ensuring that Prefect types do not leak into the Core API.
- Testing API compatibility across version changes.

Consequently, F-09 will be considered resolved through a "Public API Conformance Suite," rather than simply by standardizing folder names.