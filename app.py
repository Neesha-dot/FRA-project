"""
app.py - Backend Logic for Airavata Hydraulic Simulation
Contains all business logic, data management, and project handling
"""

class ProjectManager:
    """Manages all project-related operations"""
    
    def __init__(self):
        self.projects = self.load_recent_projects()
    
    def load_recent_projects(self):
        """Load recent projects from database or file"""
        # In a real application, this would load from a database
        # For now, returning sample data
        return [
            {
                "id": 1,
                "name": "Project A",
                "description": "AI-powered analytics system.",
                "status": "In Progress",
                "progress": 65,
                "created_date": "2024-01-15",
                "last_modified": "2024-11-28"
            },
            {
                "id": 2,
                "name": "Project B",
                "description": "Cloud-based backup solution.",
                "status": "Completed",
                "progress": 100,
                "created_date": "2024-02-10",
                "last_modified": "2024-10-20"
            },
            {
                "id": 3,
                "name": "Project C",
                "description": "Mobile app for task tracking.",
                "status": "On Hold",
                "progress": 45,
                "created_date": "2024-03-05",
                "last_modified": "2024-09-15"
            },
            {
                "id": 4,
                "name": "Project D",
                "description": "Web-based collaboration platform.",
                "status": "In Progress",
                "progress": 30,
                "created_date": "2024-04-20",
                "last_modified": "2024-12-01"
            }
        ]
    
    def get_recent_projects(self, limit=4):
        """Get the most recent projects"""
        return self.projects[:limit]
    
    def get_project_by_id(self, project_id):
        """Get a specific project by ID"""
        for project in self.projects:
            if project["id"] == project_id:
                return project
        return None
    
    def add_project(self, name, description):
        """Add a new project"""
        new_project = {
            "id": len(self.projects) + 1,
            "name": name,
            "description": description,
            "status": "In Progress",
            "progress": 0,
            "created_date": self.get_current_date(),
            "last_modified": self.get_current_date()
        }
        self.projects.insert(0, new_project)
        return new_project
    
    def update_project(self, project_id, **kwargs):
        """Update project details"""
        project = self.get_project_by_id(project_id)
        if project:
            project.update(kwargs)
            project["last_modified"] = self.get_current_date()
            return True
        return False
    
    def delete_project(self, project_id):
        """Delete a project"""
        self.projects = [p for p in self.projects if p["id"] != project_id]
    
    def get_current_date(self):
        """Get current date as string"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


class HydraulicSimulation:
    """Handles hydraulic simulation calculations"""
    
    def __init__(self):
        self.simulation_data = {}
    
    def calculate_flow_rate(self, diameter, velocity):
        """Calculate flow rate (Q = A * v)"""
        import math
        area = math.pi * (diameter / 2) ** 2
        flow_rate = area * velocity
        return flow_rate
    
    def calculate_pressure_drop(self, length, diameter, flow_rate, viscosity):
        """Calculate pressure drop using Darcy-Weisbach equation"""
        import math
        # Simplified calculation
        friction_factor = 0.02  # Assumed constant for example
        area = math.pi * (diameter / 2) ** 2
        velocity = flow_rate / area
        
        pressure_drop = (friction_factor * length * velocity ** 2) / (2 * diameter * 9.81)
        return pressure_drop
    
    def run_simulation(self, parameters):
        """Run a complete hydraulic simulation"""
        results = {
            "flow_rate": 0,
            "pressure_drop": 0,
            "reynolds_number": 0,
            "flow_regime": "",
            "success": False
        }
        
        try:
            # Extract parameters
            diameter = parameters.get("diameter", 0)
            velocity = parameters.get("velocity", 0)
            length = parameters.get("length", 0)
            viscosity = parameters.get("viscosity", 1e-6)
            
            # Perform calculations
            flow_rate = self.calculate_flow_rate(diameter, velocity)
            pressure_drop = self.calculate_pressure_drop(length, diameter, flow_rate, viscosity)
            reynolds = (velocity * diameter) / viscosity
            
            # Determine flow regime
            if reynolds < 2300:
                flow_regime = "Laminar"
            elif reynolds > 4000:
                flow_regime = "Turbulent"
            else:
                flow_regime = "Transitional"
            
            results.update({
                "flow_rate": round(flow_rate, 4),
                "pressure_drop": round(pressure_drop, 4),
                "reynolds_number": round(reynolds, 2),
                "flow_regime": flow_regime,
                "success": True
            })
            
        except Exception as e:
            results["error"] = str(e)
        
        return results


class DataValidator:
    """Validates user input and data"""
    
    @staticmethod
    def validate_positive_number(value, field_name="Value"):
        """Validate that a value is a positive number"""
        try:
            num = float(value)
            if num <= 0:
                return False, f"{field_name} must be greater than 0"
            return True, num
        except ValueError:
            return False, f"{field_name} must be a valid number"
    
    @staticmethod
    def validate_project_name(name):
        """Validate project name"""
        if not name or len(name.strip()) == 0:
            return False, "Project name cannot be empty"
        if len(name) > 100:
            return False, "Project name is too long (max 100 characters)"
        return True, name.strip()
    
    @staticmethod
    def validate_email(email):
        """Basic email validation"""
        if "@" in email and "." in email:
            return True, email
        return False, "Invalid email format"


# Utility functions
def format_number(value, decimals=2):
    """Format a number to specified decimal places"""
    return f"{value:.{decimals}f}"


def get_status_color(status):
    """Get color code for project status"""
    status_colors = {
        "Completed": "#4CAF50",
        "In Progress": "#2196F3",
        "On Hold": "#FF9800",
        "Cancelled": "#F44336"
    }
    return status_colors.get(status, "#9E9E9E")


# Example usage and testing
if __name__ == "__main__":
    # Test ProjectManager
    print("=== Testing ProjectManager ===")
    pm = ProjectManager()
    projects = pm.get_recent_projects()
    print(f"Found {len(projects)} recent projects")
    for project in projects:
        print(f"- {project['name']}: {project['status']}")
    
    # Test HydraulicSimulation
    print("\n=== Testing HydraulicSimulation ===")
    sim = HydraulicSimulation()
    params = {
        "diameter": 0.1,  # 10 cm
        "velocity": 2.0,  # 2 m/s
        "length": 10.0,   # 10 m
        "viscosity": 1e-6
    }
    results = sim.run_simulation(params)
    print(f"Flow Rate: {results['flow_rate']} m³/s")
    print(f"Pressure Drop: {results['pressure_drop']} Pa")
    print(f"Flow Regime: {results['flow_regime']}")
    
    # Test DataValidator
    print("\n=== Testing DataValidator ===")
    validator = DataValidator()
    valid, result = validator.validate_positive_number("10.5", "Diameter")
    print(f"Validation result: {valid}, Value: {result}")