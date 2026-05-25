"""Phase 1 features: Smart Commands, Prompt Studio, Agents, Health Monitoring

Revision ID: 0004
Revises: 0003
Create Date: 2025-05-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Smart Commands
    op.create_table(
        "command_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_input", sa.Text, nullable=False),
        sa.Column("suggested_command", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, default=0.0),
        sa.Column("model_used", sa.String(255), nullable=False),
        sa.Column("accepted", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )

    op.create_table(
        "command_error_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("error_output", sa.Text, nullable=False),
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("suggested_fix", sa.Text, nullable=False),
        sa.Column("fix_command", sa.Text, nullable=True),
        sa.Column("severity", sa.String(32), default="medium"),
        sa.Column("auto_fixable", sa.Boolean, default=False),
        sa.Column("model_used", sa.String(255), nullable=False),
        sa.Column("applied", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )

    op.create_table(
        "command_contexts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("command_pattern", sa.String(512), nullable=False, index=True),
        sa.Column("frequency", sa.Integer, default=1),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("context_data", JSONB, default={}),
    )

    # Prompt Studio
    op.create_table(
        "prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, default=""),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("variables", JSONB, default=[]),
        sa.Column("tags", JSONB, default=[]),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("is_public", sa.Boolean, default=True),
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("template_content", sa.Text, nullable=False),
        sa.Column("variables", JSONB, default=[]),
        sa.Column("change_notes", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("template_id", "version_number", name="uq_template_version"),
    )

    op.create_table(
        "prompt_test_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("response", sa.Text, nullable=False),
        sa.Column("tokens_input", sa.Integer, default=0),
        sa.Column("tokens_output", sa.Integer, default=0),
        sa.Column("latency_ms", sa.Integer, default=0),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )

    # Agents
    op.create_table(
        "agent_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("agent_type", sa.String(64), nullable=False, index=True),
        sa.Column("description", sa.Text, default=""),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("capabilities", JSONB, default=[]),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("max_iterations", sa.Integer, default=10),
        sa.Column("temperature", sa.Float, default=0.7),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("metadata", JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "agent_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), index=True),
        sa.Column("task", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), default="pending", index=True),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("iterations_used", sa.Integer, default=0),
        sa.Column("tokens_consumed", sa.Integer, default=0),
        sa.Column("duration_ms", sa.Integer, default=0),
        sa.Column("context_data", JSONB, default={}),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )

    op.create_table(
        "agent_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", UUID(as_uuid=True), sa.ForeignKey("agent_executions.id"), index=True),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("input_data", JSONB, default={}),
        sa.Column("output_data", JSONB, default={}),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("reasoning", sa.Text, default=""),
        sa.Column("tokens_used", sa.Integer, default=0),
        sa.Column("duration_ms", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # Health Monitoring
    op.create_table(
        "health_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("component", sa.String(128), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("response_time_ms", sa.Integer, default=0),
        sa.Column("details", JSONB, default={}),
        sa.Column("checked_at", sa.DateTime(timezone=True), index=True),
    )

    op.create_table(
        "health_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("component", sa.String(128), nullable=False, index=True),
        sa.Column("severity", sa.String(32), default="warning"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("status", sa.String(32), default="open", index=True),
        sa.Column("auto_recovery_attempted", sa.Boolean, default=False),
        sa.Column("auto_recovery_successful", sa.Boolean, default=False),
        sa.Column("recovery_action", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), index=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, default={}),
    )

    op.create_table(
        "recovery_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer, default=0),
    )


def downgrade() -> None:
    op.drop_table("recovery_actions")
    op.drop_table("health_incidents")
    op.drop_table("health_checks")
    op.drop_table("agent_steps")
    op.drop_table("agent_executions")
    op.drop_table("agent_configs")
    op.drop_table("prompt_test_results")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_templates")
    op.drop_table("command_contexts")
    op.drop_table("command_error_analyses")
    op.drop_table("command_suggestions")
