"""
Google Drive 구조 감사 및 유지 모듈 (Guardian)

정의된 폴더 구조를 기반으로 Drive 상태를 감사하고,
위반 사항을 탐지/교정합니다.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_credentials
from .project_registry import ProjectRegistry


class Severity(Enum):
    """위반 심각도"""
    CRITICAL = "critical"  # 루트에 파일 존재, 미허용 폴더
    WARNING = "warning"    # 프로젝트 하위 구조 누락
    INFO = "info"          # 빈 폴더, 분류 가능한 파일


@dataclass
class Violation:
    """구조 위반 항목"""
    severity: Severity
    category: str           # root_file, unknown_folder, missing_subfolder, misplaced_file
    message: str
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    current_location: Optional[str] = None
    suggested_action: Optional[str] = None
    suggested_target: Optional[str] = None  # 이동 대상 folder_id


@dataclass
class AuditReport:
    """감사 결과 보고서"""
    total_root_items: int = 0
    violations: list[Violation] = field(default_factory=list)
    project_status: dict[str, dict[str, int]] = field(default_factory=dict)  # project_name → {documents: N, images: N}

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.INFO)

    @property
    def is_clean(self) -> bool:
        return self.critical_count == 0 and self.warning_count == 0

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "Drive Structure Audit Report",
            "=" * 60,
            "",
            f"Root items: {self.total_root_items}",
            f"Violations: {len(self.violations)} "
            f"(CRITICAL: {self.critical_count}, WARNING: {self.warning_count}, INFO: {self.info_count})",
            "",
        ]

        if self.is_clean:
            lines.append("Status: CLEAN - No structural violations detected")
        else:
            lines.append("Status: VIOLATIONS FOUND")

        # Project status
        if self.project_status:
            lines.append("")
            lines.append("Project Status:")
            for project, status in self.project_status.items():
                docs = status.get("documents", 0)
                imgs = status.get("images", 0)
                other = status.get("other", 0)
                lines.append(f"  {project}: documents={docs}, images={imgs}, other={other}")

        # Violations by category
        if self.violations:
            lines.append("")
            lines.append("Violations:")
            for v in self.violations:
                icon = {"critical": "!!", "warning": "!", "info": "i"}[v.severity.value]
                lines.append(f"  [{icon}] {v.message}")
                if v.suggested_action:
                    lines.append(f"      -> {v.suggested_action}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class FixAction:
    """교정 작업 항목"""
    action: str             # move, create_folder
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    target_folder_id: Optional[str] = None
    target_folder_name: Optional[str] = None
    description: str = ""


@dataclass
class FixPlan:
    """교정 계획"""
    actions: list[FixAction] = field(default_factory=list)

    @property
    def move_count(self) -> int:
        return sum(1 for a in self.actions if a.action == "move")

    @property
    def create_count(self) -> int:
        return sum(1 for a in self.actions if a.action == "create_folder")

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "Fix Plan",
            "=" * 60,
            "",
            f"Total actions: {len(self.actions)}",
            f"  - Move file: {self.move_count}",
            f"  - Create folder: {self.create_count}",
            "",
        ]

        for i, action in enumerate(self.actions, 1):
            lines.append(f"  {i}. [{action.action}] {action.description}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


class DriveGuardian:
    """Google Drive 구조 감사 및 교정 도구"""

    def __init__(self):
        self.registry = ProjectRegistry()
        self.creds = get_credentials()
        self.drive = build("drive", "v3", credentials=self.creds)
        # NOTE: ProjectRegistry._config는 public getter가 없어 직접 접근
        self._config = self.registry._config
        self._governance = self._config.get("governance", {})

    def _list_children(self, folder_id: str) -> list[dict]:
        """폴더 내 직계 자식 항목 조회"""
        all_items = []
        page_token = None

        try:
            while True:
                query = f"'{folder_id}' in parents and trashed=false"
                results = self.drive.files().list(
                    q=query,
                    pageSize=200,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)"
                ).execute()

                all_items.extend(results.get("files", []))

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        except HttpError as e:
            # API 에러 시 빈 리스트 반환 (폴더 접근 불가 등)
            print(f"Warning: Drive API error for folder {folder_id}: {e}")
            return []

        return all_items

    def _get_root_folder_id(self) -> str:
        """Claude Code 연동 Drive 루트 폴더 ID"""
        projects = self.registry.list_projects()
        if not projects:
            raise RuntimeError("등록된 프로젝트가 없습니다. config/drive_projects.yaml을 확인하세요.")
        first_project = projects[0]
        folder_id = self.registry.get_folder_id(first_project)
        try:
            file = self.drive.files().get(
                fileId=folder_id, fields="parents"
            ).execute()
        except Exception as e:
            raise RuntimeError(f"Drive API 호출 실패 (folder_id={folder_id}): {e}")
        parents = file.get("parents", [])
        if parents:
            return parents[0]
        raise RuntimeError("루트 폴더를 확인할 수 없습니다")

    def _classify_by_keywords(self, filename: str) -> Optional[str]:
        """파일명에서 프로젝트를 키워드 기반으로 추론"""
        projects = self._config.get("projects", {})
        for project_name, project_config in projects.items():
            keywords = project_config.get("file_keywords", [])
            for keyword in keywords:
                if keyword.lower() in filename.lower():
                    return project_name
        return None

    def _determine_subfolder(self, mime_type: str) -> str:
        """MIME type으로 하위 폴더 결정"""
        type_routing = self._governance.get("type_routing", {})

        for pattern, subfolder in type_routing.items():
            if pattern.endswith("/*"):
                # 와일드카드 매칭 (image/*)
                prefix = pattern[:-2]
                if mime_type.startswith(prefix):
                    return subfolder
            elif mime_type == pattern:
                return subfolder

        # 기본값: documents
        return "documents"

    def _audit_root_level(
        self,
        root_items: list[dict],
        allowed_folders: list[str],
        known_folder_ids: set[str],
        files_allowed: bool,
        report: AuditReport,
    ) -> None:
        """루트 레벨 검사 (위반 사항 report에 추가)"""
        projects = self._config.get("projects", {})

        for item in root_items:
            is_folder = item["mimeType"] == "application/vnd.google-apps.folder"

            if is_folder:
                # 허용된 폴더인지 확인
                if item["name"] not in allowed_folders and item["id"] not in known_folder_ids:
                    report.violations.append(Violation(
                        severity=Severity.CRITICAL,
                        category="unknown_folder",
                        message=f"루트에 미허용 폴더: '{item['name']}'",
                        file_id=item["id"],
                        file_name=item["name"],
                        mime_type=item["mimeType"],
                        current_location="root",
                        suggested_action="_아카이브로 이동",
                        suggested_target=self._config.get("special_folders", {}).get("_아카이브", {}).get("folder_id"),
                    ))
            else:
                # 루트에 파일 존재
                if not files_allowed:
                    project = self._classify_by_keywords(item["name"])
                    if project:
                        subfolder = self._determine_subfolder(item["mimeType"])
                        target_id = projects.get(project, {}).get("subfolders", {}).get(subfolder)
                        report.violations.append(Violation(
                            severity=Severity.CRITICAL,
                            category="root_file",
                            message=f"루트에 파일: '{item['name']}' → {project}/{subfolder}",
                            file_id=item["id"],
                            file_name=item["name"],
                            mime_type=item["mimeType"],
                            current_location="root",
                            suggested_action=f"{project}/{subfolder}로 이동",
                            suggested_target=target_id,
                        ))
                    else:
                        archive_id = self._config.get("special_folders", {}).get("_아카이브", {}).get("folder_id")
                        report.violations.append(Violation(
                            severity=Severity.CRITICAL,
                            category="root_file",
                            message=f"루트에 미분류 파일: '{item['name']}'",
                            file_id=item["id"],
                            file_name=item["name"],
                            mime_type=item["mimeType"],
                            current_location="root",
                            suggested_action="_아카이브로 이동",
                            suggested_target=archive_id,
                        ))

    def _audit_project_structure(
        self,
        project_name: str,
        project_config: dict,
        required_subs: list[str],
        report: AuditReport,
    ) -> None:
        """프로젝트별 하위 구조 검사 (위반 사항 report에 추가)"""
        project_folder_id = project_config["folder_id"]
        children = self._list_children(project_folder_id)

        child_names = {c["name"]: c for c in children if c["mimeType"] == "application/vnd.google-apps.folder"}
        child_files = [c for c in children if c["mimeType"] != "application/vnd.google-apps.folder"]

        status = {"documents": 0, "images": 0, "other": 0}

        # 필수 하위 폴더 존재 확인
        for sub_name in required_subs:
            if sub_name not in child_names:
                report.violations.append(Violation(
                    severity=Severity.WARNING,
                    category="missing_subfolder",
                    message=f"'{project_name}'에 필수 하위 폴더 누락: {sub_name}",
                    current_location=project_name,
                    suggested_action=f"'{sub_name}' 폴더 생성",
                ))

        # 하위 폴더 내 파일 수 집계
        for sub_name in ["documents", "images"]:
            sub_id = project_config.get("subfolders", {}).get(sub_name)
            if sub_id:
                sub_files = self._list_children(sub_id)
                status[sub_name] = len(sub_files)

        # 프로젝트 루트에 직접 파일이 있으면 경고
        for f in child_files:
            subfolder = self._determine_subfolder(f["mimeType"])
            target_id = project_config.get("subfolders", {}).get(subfolder)
            report.violations.append(Violation(
                severity=Severity.INFO,
                category="misplaced_file",
                message=f"'{project_name}' 루트에 파일: '{f['name']}' → {subfolder}/",
                file_id=f["id"],
                file_name=f["name"],
                mime_type=f["mimeType"],
                current_location=project_name,
                suggested_action=f"{project_name}/{subfolder}로 이동",
                suggested_target=target_id,
            ))
            status["other"] += 1

        report.project_status[project_name] = status

    def audit(self) -> AuditReport:
        """전체 Drive 구조 감사"""
        report = AuditReport()

        root_id = self._get_root_folder_id()
        root_items = self._list_children(root_id)
        report.total_root_items = len(root_items)

        # 허용된 폴더 목록
        root_policy = self._governance.get("root_policy", {})
        allowed_folders = root_policy.get("allowed_folders", [])
        files_allowed = root_policy.get("files_allowed", True)

        # 모든 등록된 폴더 ID 수집
        known_folder_ids = set()
        projects = self._config.get("projects", {})
        for p_config in projects.values():
            known_folder_ids.add(p_config["folder_id"])
        special = self._config.get("special_folders", {})
        for s_config in special.values():
            known_folder_ids.add(s_config["folder_id"])

        # 1. 루트 레벨 검사
        self._audit_root_level(root_items, allowed_folders, known_folder_ids, files_allowed, report)

        # 2. 프로젝트별 하위 구조 검사
        required_subs = self._governance.get("required_subfolders", ["documents", "images"])
        for project_name, project_config in projects.items():
            self._audit_project_structure(project_name, project_config, required_subs, report)

        return report

    def generate_fix_plan(self, report: AuditReport) -> FixPlan:
        """감사 결과에서 교정 계획 생성"""
        plan = FixPlan()

        for v in report.violations:
            if v.category == "missing_subfolder":
                plan.actions.append(FixAction(
                    action="create_folder",
                    description=v.message,
                ))
            elif v.file_id and v.suggested_target:
                plan.actions.append(FixAction(
                    action="move",
                    file_id=v.file_id,
                    file_name=v.file_name,
                    target_folder_id=v.suggested_target,
                    description=f"'{v.file_name}' → {v.suggested_action}",
                ))

        return plan

    def apply_fixes(self, plan: FixPlan, dry_run: bool = True) -> dict:
        """교정 계획 실행"""
        result = {
            "dry_run": dry_run,
            "total_actions": len(plan.actions),
            "applied": [],
            "errors": [],
        }

        for action in plan.actions:
            if action.action == "move" and action.file_id and action.target_folder_id:
                if dry_run:
                    result["applied"].append({
                        "action": "move",
                        "file": action.file_name,
                        "target": action.target_folder_id,
                        "status": "dry_run",
                    })
                else:
                    try:
                        file = self.drive.files().get(
                            fileId=action.file_id, fields="parents"
                        ).execute()
                        previous_parents = ",".join(file.get("parents", []))

                        self.drive.files().update(
                            fileId=action.file_id,
                            addParents=action.target_folder_id,
                            removeParents=previous_parents,
                            fields="id, parents"
                        ).execute()

                        result["applied"].append({
                            "action": "move",
                            "file": action.file_name,
                            "target": action.target_folder_id,
                            "status": "done",
                        })
                    except Exception as e:
                        result["errors"].append({
                            "action": "move",
                            "file": action.file_name,
                            "target": action.target_folder_id,
                            "error": f"{type(e).__name__}: {e}",
                        })

            elif action.action == "create_folder":
                result["applied"].append({
                    "action": "create_folder",
                    "description": action.description,
                    "status": "dry_run" if dry_run else "skipped",
                })

        return result


def print_audit_report(report: AuditReport):
    """감사 보고서 출력 (CLI용)"""
    print(report.summary())


def print_fix_plan(plan: FixPlan):
    """교정 계획 출력 (CLI용)"""
    print(plan.summary())
