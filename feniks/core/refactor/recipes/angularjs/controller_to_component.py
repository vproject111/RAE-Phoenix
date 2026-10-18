# Copyright 2025 Grzegorz Leśniowski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Controller to Component Recipe - Migrates AngularJS controllers to Next.js components.

Handles:
- Controller functions → Functional React components
- $scope → useState/useReducer
- DI services → Import statements
- Lifecycle hooks → useEffect
- Navigation → next/navigation hooks
"""
from typing import List, Dict, Any, Optional
import re
from pathlib import Path
from dataclasses import dataclass

from feniks.core.refactor.recipe import (
    RefactorRecipe, RefactorPlan, RefactorResult, RefactorRisk, FileChange
)
from feniks.core.models.types import SystemModel, Module, Chunk
from feniks.infra.logging import get_logger

log = get_logger("refactor.recipes.angularjs.controller_to_component")


@dataclass
class ControllerMetadata:
    """Metadata extracted from an AngularJS controller."""
    name: str
    module_name: str
    dependencies: List[str]
    properties: Dict[str, Any]
    methods: Dict[str, str]
    controller_as: Optional[str]
    template_path: Optional[str]
    uses_scope: bool
    lifecycle_hooks: List[str]


class ControllerToComponentRecipe(RefactorRecipe):
    """
    Recipe for migrating AngularJS controllers to Next.js functional components.

    Mapping strategy:
    - Controller → Functional component
    - $scope properties → useState
    - $scope methods → Component functions
    - DI services → Import statements
    - $http → fetch or axios
    - $state/$stateParams → useRouter/useSearchParams
    - $timeout → setTimeout in useEffect
    - $scope.$on('$destroy') → useEffect cleanup
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the recipe.

        Args:
            config: Optional configuration with:
                - target_dir: Target directory for components (default: "app/_legacy")
                - state_strategy: "useState" | "useReducer" | "external-store"
                - typing_mode: "loose" | "strict"
                - aggressiveness: "conservative" | "balanced" | "aggressive"
        """
        super().__init__()
        self.config = config or {}
        self.target_dir = self.config.get("target_dir", "app/_legacy")
        self.state_strategy = self.config.get("state_strategy", "useState")
        self.typing_mode = self.config.get("typing_mode", "strict")
        self.aggressiveness = self.config.get("aggressiveness", "balanced")

    @property
    def name(self) -> str:
        return "angularjs.controller-to-next-component"

    @property
    def description(self) -> str:
        return "Migrate AngularJS controllers to Next.js functional components with TypeScript"

    @property
    def risk_level(self) -> RefactorRisk:
        return RefactorRisk.MEDIUM

    def analyze(
        self,
        system_model: SystemModel,
        target: Optional[Dict[str, Any]] = None
    ) -> Optional[RefactorPlan]:
        """
        Analyze the system to find AngularJS controllers.

        Args:
            system_model: The system model
            target: Optional dict with 'controller_name' or 'module_name'

        Returns:
            RefactorPlan or None
        """
        log.info(f"Analyzing for AngularJS controllers: {system_model.project}")

        # Find controllers in the codebase
        controllers = self._find_controllers(system_model, target)

        if not controllers:
            log.info("No AngularJS controllers found")
            return None

        # Extract metadata for all controllers
        controller_metadata = []
        target_files = []

        for controller_chunk in controllers:
            metadata = self._extract_controller_metadata(controller_chunk)
            if metadata:
                controller_metadata.append(metadata)
                target_files.append(controller_chunk.file_path)

        if not controller_metadata:
            log.info("No valid controller metadata extracted")
            return None

        # Assess risks
        risks = self._assess_risks(controller_metadata)
        risk_level = self._calculate_risk_level(controller_metadata)

        # Create refactoring plan
        plan = RefactorPlan(
            recipe_name=self.name,
            project=system_model.project,
            target_modules=[m.name for m in controller_metadata],
            target_files=list(set(target_files)),
            rationale=f"Migrate {len(controller_metadata)} AngularJS controllers to Next.js components",
            risks=risks,
            risk_level=risk_level,
            estimated_changes=len(controller_metadata) * 2,  # Controller file + component file
            validation_steps=[
                "Verify TypeScript compilation",
                "Check all imports are resolved",
                "Validate component props interfaces",
                "Run Behavior Guard tests",
                "Manual review of generated components"
            ],
            metadata={
                "controllers": [
                    {
                        "name": m.name,
                        "module": m.module_name,
                        "dependencies": m.dependencies,
                        "template": m.template_path
                    }
                    for m in controller_metadata
                ],
                "target_directory": self.target_dir,
                "state_strategy": self.state_strategy,
                "typing_mode": self.typing_mode
            }
        )

        log.info(f"Created refactoring plan for {len(controller_metadata)} controllers")
        return plan

    def execute(
        self,
        plan: RefactorPlan,
        chunks: List[Chunk],
        dry_run: bool = True
    ) -> RefactorResult:
        """
        Execute the controller-to-component migration.

        Args:
            plan: The refactoring plan
            chunks: Code chunks containing controllers
            dry_run: If True, don't write files

        Returns:
            RefactorResult with generated components
        """
        log.info(f"Executing controller migration (dry_run={dry_run})")

        result = RefactorResult(plan=plan, success=True)

        try:
            for controller_data in plan.metadata["controllers"]:
                # Find the corresponding chunk
                controller_chunk = self._find_chunk_by_name(chunks, controller_data["name"])
                if not controller_chunk:
                    result.warnings.append(f"Could not find chunk for controller: {controller_data['name']}")
                    continue

                # Extract full metadata
                metadata = self._extract_controller_metadata(controller_chunk)
                if not metadata:
                    result.warnings.append(f"Could not extract metadata for: {controller_data['name']}")
                    continue

                # Generate Next.js component
                component_code = self._generate_component(metadata, plan)
                component_path = self._get_component_path(metadata)

                # Create file change
                file_change = FileChange(
                    file_path=component_path,
                    original_content="",  # New file
                    modified_content=component_code,
                    change_type="create"
                )
                result.file_changes.append(file_change)

                # Delete original controller file
                delete_change = FileChange(
                    file_path=controller_chunk.file_path,
                    original_content=controller_chunk.text,
                    modified_content="",
                    change_type="delete"
                )
                result.file_changes.append(delete_change)

                # Generate mapping metadata
                if "component_mapping" not in result.metadata:
                    result.metadata["component_mapping"] = {}

                result.metadata["component_mapping"][metadata.name] = {
                    "controller": controller_chunk.file_path,
                    "component": component_path,
                    "template": metadata.template_path
                }

                log.info(f"Generated component: {component_path}")

        except Exception as e:
            log.error(f"Error during execution: {e}", exc_info=True)
            result.success = False
            result.errors.append(str(e))

        return result

    def validate(self, result: RefactorResult) -> bool:
        """
        Validate the migration result.

        Args:
            result: The refactoring result

        Returns:
            bool: True if validation passed
        """
        log.info("Validating controller migration")

        validation_results = {}

        # Check all files were generated (created or modified components)
        created_changes = [c for c in result.file_changes if c.change_type in ("create", "modify")]
        validation_results["all_files_generated"] = len(created_changes) == len(
            result.plan.metadata["controllers"]
        )

        # Check TypeScript syntax (basic check)
        for file_change in created_changes:
            syntax_valid = self._validate_typescript_syntax(file_change.modified_content)
            validation_results[f"syntax_{Path(file_change.file_path).name}"] = syntax_valid

        # Check imports
        for file_change in created_changes:
            imports_valid = self._validate_imports(file_change.modified_content)
            validation_results[f"imports_{Path(file_change.file_path).name}"] = imports_valid

        result.validation_results = validation_results

        # Overall validation passes if all checks pass
        all_passed = all(validation_results.values())

        if all_passed:
            log.info("Validation passed")
        else:
            failed = [k for k, v in validation_results.items() if not v]
            log.warning(f"Validation failed for: {failed}")

        return all_passed

    # Helper methods

    def _find_controllers(
        self,
        system_model: SystemModel,
        target: Optional[Dict[str, Any]]
    ) -> List[Chunk]:
        """Find AngularJS controller definitions in the codebase."""
        controllers = []

        for module_name, module in system_model.modules.items():
            # Skip if target specified and doesn't match
            if target and "module_name" in target:
                if module_name != target["module_name"]:
                    continue

            for chunk in module.chunks:
                # Look for controller registration patterns
                if self._is_controller_chunk(chunk):
                    # Check if specific controller targeted
                    if target and "controller_name" in target:
                        if target["controller_name"] not in chunk.content:
                            continue
                    controllers.append(chunk)

        return controllers

    def _is_controller_chunk(self, chunk: Chunk) -> bool:
        """Check if a chunk contains an AngularJS controller definition."""
        # Patterns for controller registration
        patterns = [
            r'\.controller\s*\(\s*["\'](\w+)["\']',  # .controller('NameCtrl', ...)
            r'angular\.module\([^)]+\)\.controller',  # angular.module(...).controller
        ]

        for pattern in patterns:
            if re.search(pattern, chunk.content):
                return True

        return False

    def _extract_controller_metadata(self, chunk: Chunk) -> Optional[ControllerMetadata]:
        """Extract metadata from a controller chunk."""
        try:
            # Extract controller name
            name_match = re.search(r'\.controller\s*\(\s*["\'](\w+)["\']', chunk.content)
            if not name_match:
                return None

            controller_name = name_match.group(1)

            # Extract module name (if available)
            module_match = re.search(r'angular\.module\s*\(\s*["\']([^"\']+)["\']', chunk.content)
            module_name = module_match.group(1) if module_match else "unknown"

            # Extract dependencies from DI
            dependencies = self._extract_dependencies(chunk.content)

            # Extract properties and methods
            properties, methods = self._extract_properties_and_methods(chunk.content)

            # Check for controllerAs syntax
            controller_as = self._extract_controller_as(chunk.content)

            # Check if uses $scope
            uses_scope = "$scope" in dependencies

            # Extract lifecycle hooks
            lifecycle_hooks = self._extract_lifecycle_hooks(chunk.content)

            # Try to find associated template
            template_path = self._find_template_path(chunk)

            return ControllerMetadata(
                name=controller_name,
                module_name=module_name,
                dependencies=dependencies,
                properties=properties,
                methods=methods,
                controller_as=controller_as,
                template_path=template_path,
                uses_scope=uses_scope,
                lifecycle_hooks=lifecycle_hooks
            )

        except Exception as e:
            log.error(f"Error extracting controller metadata: {e}", exc_info=True)
            return None

    def _extract_dependencies(self, content: str) -> List[str]:
        """Extract DI dependencies from controller."""
        dependencies = []

        # Pattern 1: Array notation ['$scope', '$http', function($scope, $http) { ... }]
        array_match = re.search(r'\[([^\]]+)\s*,\s*function', content)
        if array_match:
            deps_str = array_match.group(1)
            dependencies = [d.strip().strip('"\'') for d in deps_str.split(',')]

        # Pattern 2: Function parameters function($scope, $http) { ... }
        else:
            func_match = re.search(r'function\s*\(([^)]*)\)', content)
            if func_match:
                params = func_match.group(1)
                dependencies = [p.strip() for p in params.split(',') if p.strip()]

        return dependencies

    def _extract_properties_and_methods(self, content: str) -> tuple:
        """Extract properties and methods from controller."""
        properties = {}
        methods = {}

        # Look for this.prop = value or $scope.prop = value
        prop_pattern = r'(?:this|(?:\$scope))\.(\w+)\s*=\s*([^;]+);'
        for match in re.finditer(prop_pattern, content):
            prop_name = match.group(1)
            prop_value = match.group(2).strip()

            # Check if it's a function
            if prop_value.startswith('function'):
                methods[prop_name] = prop_value
            else:
                properties[prop_name] = prop_value

        return properties, methods

    def _extract_controller_as(self, content: str) -> Optional[str]:
        """Extract controllerAs alias if present."""
        # Look for controllerAs in route config or directive
        match = re.search(r'controllerAs\s*:\s*["\'](\w+)["\']', content)
        return match.group(1) if match else None

    def _extract_lifecycle_hooks(self, content: str) -> List[str]:
        """Extract lifecycle hooks used in controller."""
        hooks = []

        if "$scope.$on('$destroy'" in content:
            hooks.append("$destroy")
        if "$scope.$on('$init'" in content:
            hooks.append("$init")
        if "$timeout" in content or "$interval" in content:
            hooks.append("timer")

        return hooks

    def _find_template_path(self, chunk: Chunk) -> Optional[str]:
        """Try to find associated template path."""
        # Look in same directory as controller
        template_patterns = [
            r'templateUrl\s*:\s*["\']([^"\']+)["\']',
            r'template\s*:\s*["\']([^"\']+)["\']'
        ]

        for pattern in template_patterns:
            match = re.search(pattern, chunk.content)
            if match:
                return match.group(1)

        return None

    def _assess_risks(self, controllers: List[ControllerMetadata]) -> List[str]:
        """Assess risks for the migration."""
        risks = []

        # Check for complex patterns
        for controller in controllers:
            if len(controller.dependencies) > 5:
                risks.append(f"Controller {controller.name} has many dependencies ({len(controller.dependencies)})")

            if "$rootScope" in controller.dependencies:
                risks.append(f"Controller {controller.name} uses $rootScope (global state)")

            if "$watch" in str(controller.methods):
                risks.append(f"Controller {controller.name} uses watchers")

            if not controller.template_path:
                risks.append(f"Controller {controller.name} has no associated template")

        # Generic risks
        risks.extend([
            "May require manual adjustment of service imports",
            "State management might need refactoring for complex cases",
            "Event handlers need manual review for proper binding"
        ])

        return risks

    def _calculate_risk_level(self, controllers: List[ControllerMetadata]) -> RefactorRisk:
        """Calculate overall risk level."""
        high_risk_count = 0

        for controller in controllers:
            if len(controller.dependencies) > 7:
                high_risk_count += 1
            if "$rootScope" in controller.dependencies:
                high_risk_count += 1
            if len(controller.lifecycle_hooks) > 2:
                high_risk_count += 1

        if high_risk_count > len(controllers) / 2:
            return RefactorRisk.HIGH
        elif high_risk_count > 0:
            return RefactorRisk.MEDIUM
        else:
            return RefactorRisk.LOW

    def _find_chunk_by_name(self, chunks: List[Chunk], name: str) -> Optional[Chunk]:
        """Find a chunk by controller name."""
        for chunk in chunks:
            if f"'{name}'" in chunk.content or f'"{name}"' in chunk.content:
                return chunk
        return None

    def _generate_component(self, metadata: ControllerMetadata, plan: RefactorPlan) -> str:
        """Generate Next.js component code from controller metadata."""
        component_name = self._to_component_name(metadata.name)

        # Generate imports
        imports = self._generate_imports(metadata)

        # Generate props interface
        props_interface = self._generate_props_interface(metadata, component_name)

        # Generate state declarations
        state_declarations = self._generate_state_declarations(metadata)

        # Generate methods
        methods = self._generate_methods(metadata)

        # Generate effects
        effects = self._generate_effects(metadata)

        # Generate JSX (placeholder)
        jsx = self._generate_jsx_placeholder(metadata)

        # Compose component
        component = f"""// Generated by Feniks - AngularJS Controller to Next.js Component
// Source controller: {metadata.name}
// Module: {metadata.module_name}
//
// TODO: Review and adjust the generated code
// TODO: Connect with migrated template (JSX)
// TODO: Verify all service imports

{imports}

{props_interface}

export default function {component_name}(props: {component_name}Props) {{
{state_declarations}

{methods}

{effects}

  return (
{jsx}
  );
}}
"""

        return component

    def _to_component_name(self, controller_name: str) -> str:
        """Convert controller name to component name."""
        # Remove Ctrl/Controller suffix
        name = re.sub(r'(Ctrl|Controller)$', '', controller_name)
        # Add Page suffix if not present
        if not name.endswith('Page') and not name.endswith('View'):
            name += 'Page'
        return name

    def _generate_imports(self, metadata: ControllerMetadata) -> str:
        """Generate import statements."""
        imports = ['import React, { useState, useEffect } from "react";']

        # Check for navigation dependencies
        if any(dep in ['$state', '$stateParams', '$location'] for dep in metadata.dependencies):
            imports.append('import { useRouter, useSearchParams } from "next/navigation";')

        # Generate service imports
        for dep in metadata.dependencies:
            if dep not in ['$scope', '$http', '$timeout', '$interval', '$q', '$state', '$stateParams', '$location', '$rootScope']:
                # Custom service
                service_name = dep.replace('$', '').capitalize()
                imports.append(f'// TODO: import {{ {service_name} }} from "@/legacy/services/{service_name}";')

        return '\n'.join(imports)

    def _generate_props_interface(self, metadata: ControllerMetadata, component_name: str) -> str:
        """Generate TypeScript props interface."""
        if self.typing_mode == "strict":
            return f"""interface {component_name}Props {{
  // TODO: Add props based on route params and parent requirements
  // Example: id?: string;
}}"""
        else:
            return f"""interface {component_name}Props {{
  [key: string]: any; // Loose typing
}}"""

    def _generate_state_declarations(self, metadata: ControllerMetadata) -> str:
        """Generate useState declarations."""
        declarations = []

        for prop_name, prop_value in metadata.properties.items():
            # Try to infer type
            type_hint = self._infer_type(prop_value)

            if self.state_strategy == "useState":
                declarations.append(
                    f"  const [{prop_name}, set{prop_name.capitalize()}] = useState<{type_hint}>({prop_value});"
                )

        if not declarations:
            declarations.append("  // TODO: Add state based on controller properties")

        return '\n'.join(declarations)

    def _infer_type(self, value: str) -> str:
        """Infer TypeScript type from value."""
        value = value.strip()

        if value in ['true', 'false']:
            return 'boolean'
        elif value.startswith('['):
            return 'any[]'
        elif value.startswith('{'):
            return 'any'
        elif value.startswith('"') or value.startswith("'"):
            return 'string'
        elif value.isdigit():
            return 'number'
        else:
            return 'any'

    def _generate_methods(self, metadata: ControllerMetadata) -> str:
        """Generate component methods."""
        methods = []

        for method_name, method_body in metadata.methods.items():
            methods.append(f"""  const {method_name} = () => {{
    // TODO: Implement {method_name}
    // Original: {method_body[:50]}...
  }};""")

        if not methods:
            methods.append("  // TODO: Add methods from controller")

        return '\n\n'.join(methods)

    def _generate_effects(self, metadata: ControllerMetadata) -> str:
        """Generate useEffect hooks."""
        effects = []

        # Lifecycle hooks
        if '$destroy' in metadata.lifecycle_hooks:
            effects.append("""  useEffect(() => {
    // Component mount logic

    return () => {
      // Cleanup (from $scope.$on('$destroy'))
      // TODO: Add cleanup logic
    };
  }, []);""")

        if not effects:
            effects.append("""  useEffect(() => {
    // TODO: Add effects for initialization and cleanup
  }, []);""")

        return '\n\n'.join(effects)

    def _generate_jsx_placeholder(self, metadata: ControllerMetadata) -> str:
        """Generate JSX placeholder."""
        template_note = f"Template: {metadata.template_path}" if metadata.template_path else "No template found"

        return f"""    <div>
      {{/* TODO: Replace with migrated template */}}
      {{/* {template_note} */}}
      <h1>{self._to_component_name(metadata.name)}</h1>
      <p>Controller migrated from AngularJS</p>
    </div>"""

    def _get_component_path(self, metadata: ControllerMetadata) -> str:
        """Get the target path for the component."""
        component_name = self._to_component_name(metadata.name)
        # Convert to kebab-case for directory
        dir_name = re.sub(r'(?<!^)(?=[A-Z])', '-', component_name.replace('Page', '').replace('View', '')).lower()
        return f"{self.target_dir}/{dir_name}/{component_name}.tsx"

    def _validate_typescript_syntax(self, content: str) -> bool:
        """Basic TypeScript syntax validation."""
        # Check for basic syntax errors
        if content.count('{') != content.count('}'):
            return False
        if content.count('(') != content.count(')'):
            return False
        if content.count('[') != content.count(']'):
            return False

        # Check required elements
        if 'export default function' not in content:
            return False

        return True

    def _validate_imports(self, content: str) -> bool:
        """Validate import statements."""
        # Check for React import
        if 'import React' not in content and 'import {' not in content:
            return False

        return True
