"""Public API placeholder.

Implementation task: 10_Dependency_Packaging_Public_API
Related diagrams:
  class: 03_Diagrams_Codes_Files/10_Dependency_Packaging_Public_API.dot
  association: C_Association_Diagram_Code/10_Dependency_Packaging_Public_API_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/01_Package_Module_Dependency_Graph.dot

Curated stable Public API boundary. Core Public API and Prefect Integration Public API
are separable; Core must remain usable with Prefect absent.
"""


class CorePublicAPI:
    """Core public API surface; no Prefect types leak into Core API (placeholder)."""
    pass


class IntegrationPublicAPI:
    """Prefect Integration public API boundary (placeholder)."""
    pass
