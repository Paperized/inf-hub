import json
import urllib.request
import urllib.error


class InfisicalAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/api"):
            self.base_url = self.base_url[:-4]
        self.token = token

    def _request(self, method, path, body=None):
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            try:
                error_json = json.loads(error_body)
                msg = error_json.get("message", error_body)
            except json.JSONDecodeError:
                msg = error_body
            raise RuntimeError(f"API error {e.code}: {msg}") from e

    def create_project(self, project_name, org_id=None, slug=None):
        body = {"projectName": project_name}
        if org_id:
            body["organizationId"] = org_id
        if slug:
            body["slug"] = slug
        return self._request("POST", "/api/v1/projects", body)

    def list_projects(self):
        return self._request("GET", "/api/v1/projects")

    def add_identity_to_project(self, project_id, identity_id, role):
        body = {"role": role}
        return self._request(
            "POST",
            f"/api/v1/projects/{project_id}/memberships/identities/{identity_id}",
            body,
        )

    def list_organizations(self):
        result = self._request("GET", "/api/v1/projects")
        projects = result.get("projects", [])
        orgs = {}
        for project in projects:
            org_id = project.get("orgId")
            if org_id and org_id not in orgs:
                orgs[org_id] = {"id": org_id, "name": org_id, "projects": []}
            if org_id:
                orgs[org_id]["projects"].append(project["name"])
        return {"organizations": list(orgs.values())}

    def list_identities(self, org_id):
        return self._request("GET", f"/api/v1/identities?orgId={org_id}")

    def list_secrets(self, project_id, environment, secret_path="/"):
        params = f"projectId={project_id}&environment={environment}&secretPath={secret_path}&viewSecretValue=true&expandSecretReferences=true"
        return self._request("GET", f"/api/v4/secrets?{params}")

    def get_secret(self, project_id, environment, secret_name, version=None, secret_path="/"):
        params = f"projectId={project_id}&environment={environment}&secretPath={secret_path}"
        if version:
            params += f"&version={version}"
        return self._request("GET", f"/api/v4/secrets/{secret_name}?{params}")

    def update_secret(self, project_id, environment, secret_name, secret_value, secret_path="/"):
        body = {
            "projectId": project_id,
            "environment": environment,
            "secretValue": secret_value,
            "secretPath": secret_path,
        }
        return self._request("PATCH", f"/api/v4/secrets/{secret_name}", body)

    def create_secret(self, project_id, environment, secret_name, secret_value, secret_path="/"):
        body = {
            "projectId": project_id,
            "environment": environment,
            "secretValue": secret_value,
            "secretPath": secret_path,
        }
        return self._request("POST", f"/api/v4/secrets/{secret_name}", body)

    def resolve_project(self, project_id):
        result = self.list_projects()
        for p in result.get("projects", []):
            if p["id"] == project_id:
                return {"id": p["id"], "name": p["name"], "slug": p["slug"]}
        return None

    def resolve_identity(self, identity_id):
        result = self._request("POST", "/api/v2/identities/search", {"scope": ["organization", "project"]})
        for i in result.get("identities", []):
            if i.get("identityId") == identity_id or i.get("id") == identity_id:
                return {"id": identity_id, "name": i["identity"]["name"]}
        return None

    def resolve_org(self, org_id):
        result = self.list_projects()
        for p in result.get("projects", []):
            if p.get("orgId") == org_id:
                return {"id": org_id, "name": org_id}
        return None

    def resolve_environment(self, project_id, env_slug):
        result = self.list_projects()
        for p in result.get("projects", []):
            if p["id"] == project_id:
                for env in p.get("environments", []):
                    if env["slug"] == env_slug:
                        return {"slug": env["slug"], "name": env["name"]}
        return None
