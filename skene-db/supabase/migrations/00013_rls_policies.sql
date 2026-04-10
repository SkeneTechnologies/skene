-- =============================================================================
-- Migration: 00013_rls_policies
-- Description: Row Level Security policies for every table.
--              Base pattern: org isolation via get_user_org_id().
--              Delete restricted to admin/owner via is_admin().
-- =============================================================================

-- =============================================================================
-- IDENTITY MODULE
-- =============================================================================

-- organizations (special case: no org_id column)
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "organizations_select" ON public.organizations
  FOR SELECT USING (
    id IN (SELECT org_id FROM public.users WHERE auth_id = auth.uid())
  );

CREATE POLICY "organizations_insert" ON public.organizations
  FOR INSERT WITH CHECK (true);

CREATE POLICY "organizations_update" ON public.organizations
  FOR UPDATE USING (
    id IN (SELECT org_id FROM public.users WHERE auth_id = auth.uid())
    AND public.is_admin()
  ) WITH CHECK (
    id IN (SELECT org_id FROM public.users WHERE auth_id = auth.uid())
  );

CREATE POLICY "organizations_delete" ON public.organizations
  FOR DELETE USING (
    id IN (SELECT org_id FROM public.users WHERE auth_id = auth.uid())
    AND public.get_user_role() = 'owner'
  );

-- users (special case: can update own record)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select" ON public.users
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "users_insert" ON public.users
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "users_update" ON public.users
  FOR UPDATE USING (
    org_id = public.get_user_org_id()
    AND (auth_id = auth.uid() OR public.is_admin())
  ) WITH CHECK (
    org_id = public.get_user_org_id()
  );

CREATE POLICY "users_delete" ON public.users
  FOR DELETE USING (
    org_id = public.get_user_org_id() AND public.is_admin()
  );

-- teams
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "teams_select" ON public.teams
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "teams_insert" ON public.teams
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "teams_update" ON public.teams
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "teams_delete" ON public.teams
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- memberships (special case: only admin/owner can invite)
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;

CREATE POLICY "memberships_select" ON public.memberships
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "memberships_insert" ON public.memberships
  FOR INSERT WITH CHECK (
    org_id = public.get_user_org_id() AND public.is_admin()
  );

CREATE POLICY "memberships_update" ON public.memberships
  FOR UPDATE USING (
    org_id = public.get_user_org_id()
    AND (user_id = (SELECT id FROM public.users WHERE auth_id = auth.uid() LIMIT 1) OR public.is_admin())
  ) WITH CHECK (
    org_id = public.get_user_org_id()
  );

CREATE POLICY "memberships_delete" ON public.memberships
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- roles
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "roles_select" ON public.roles
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "roles_insert" ON public.roles
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY "roles_update" ON public.roles
  FOR UPDATE USING (org_id = public.get_user_org_id() AND public.is_admin())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "roles_delete" ON public.roles
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- permissions
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "permissions_select" ON public.permissions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "permissions_insert" ON public.permissions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id() AND public.is_admin());

CREATE POLICY "permissions_update" ON public.permissions
  FOR UPDATE USING (org_id = public.get_user_org_id() AND public.is_admin())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "permissions_delete" ON public.permissions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- CRM MODULE
-- =============================================================================

-- contacts
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "contacts_select" ON public.contacts
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "contacts_insert" ON public.contacts
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "contacts_update" ON public.contacts
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "contacts_delete" ON public.contacts
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- companies
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "companies_select" ON public.companies
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "companies_insert" ON public.companies
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "companies_update" ON public.companies
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "companies_delete" ON public.companies
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- contact_companies
ALTER TABLE public.contact_companies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "contact_companies_select" ON public.contact_companies
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "contact_companies_insert" ON public.contact_companies
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "contact_companies_update" ON public.contact_companies
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "contact_companies_delete" ON public.contact_companies
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- PIPELINE MODULE
-- =============================================================================

-- pipelines
ALTER TABLE public.pipelines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pipelines_select" ON public.pipelines
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_insert" ON public.pipelines
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_update" ON public.pipelines
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipelines_delete" ON public.pipelines
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- pipeline_stages
ALTER TABLE public.pipeline_stages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pipeline_stages_select" ON public.pipeline_stages
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_insert" ON public.pipeline_stages
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_update" ON public.pipeline_stages
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "pipeline_stages_delete" ON public.pipeline_stages
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- deals
ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deals_select" ON public.deals
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "deals_insert" ON public.deals
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deals_update" ON public.deals
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deals_delete" ON public.deals
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- deal_stage_history
ALTER TABLE public.deal_stage_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deal_stage_history_select" ON public.deal_stage_history
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_insert" ON public.deal_stage_history
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_update" ON public.deal_stage_history
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "deal_stage_history_delete" ON public.deal_stage_history
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- TASKS MODULE
-- =============================================================================

-- projects
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "projects_select" ON public.projects
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "projects_insert" ON public.projects
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "projects_update" ON public.projects
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "projects_delete" ON public.projects
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- tasks
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tasks_select" ON public.tasks
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "tasks_insert" ON public.tasks
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tasks_update" ON public.tasks
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tasks_delete" ON public.tasks
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- task_dependencies
ALTER TABLE public.task_dependencies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "task_dependencies_select" ON public.task_dependencies
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "task_dependencies_insert" ON public.task_dependencies
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "task_dependencies_update" ON public.task_dependencies
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "task_dependencies_delete" ON public.task_dependencies
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- SUPPORT MODULE
-- =============================================================================

-- tickets
ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tickets_select" ON public.tickets
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "tickets_insert" ON public.tickets
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tickets_update" ON public.tickets
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tickets_delete" ON public.tickets
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- COMMS MODULE
-- =============================================================================

-- threads
ALTER TABLE public.threads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "threads_select" ON public.threads
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "threads_insert" ON public.threads
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "threads_update" ON public.threads
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "threads_delete" ON public.threads
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- messages
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "messages_select" ON public.messages
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "messages_insert" ON public.messages
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "messages_update" ON public.messages
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "messages_delete" ON public.messages
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- CONTENT MODULE
-- =============================================================================

-- folders
ALTER TABLE public.folders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "folders_select" ON public.folders
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "folders_insert" ON public.folders
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "folders_update" ON public.folders
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "folders_delete" ON public.folders
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- documents
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "documents_select" ON public.documents
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "documents_insert" ON public.documents
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "documents_update" ON public.documents
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "documents_delete" ON public.documents
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- comments
ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "comments_select" ON public.comments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "comments_insert" ON public.comments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "comments_update" ON public.comments
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "comments_delete" ON public.comments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- BILLING MODULE
-- =============================================================================

-- products
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "products_select" ON public.products
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "products_insert" ON public.products
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "products_update" ON public.products
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "products_delete" ON public.products
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- prices
ALTER TABLE public.prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "prices_select" ON public.prices
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "prices_insert" ON public.prices
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "prices_update" ON public.prices
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "prices_delete" ON public.prices
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- subscriptions
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "subscriptions_select" ON public.subscriptions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "subscriptions_insert" ON public.subscriptions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "subscriptions_update" ON public.subscriptions
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "subscriptions_delete" ON public.subscriptions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- invoices
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "invoices_select" ON public.invoices
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "invoices_insert" ON public.invoices
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "invoices_update" ON public.invoices
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "invoices_delete" ON public.invoices
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- payments
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "payments_select" ON public.payments
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "payments_insert" ON public.payments
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "payments_update" ON public.payments
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "payments_delete" ON public.payments
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- CALENDAR MODULE
-- =============================================================================

-- events
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "events_select" ON public.events
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "events_insert" ON public.events
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "events_update" ON public.events
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "events_delete" ON public.events
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- event_attendees
ALTER TABLE public.event_attendees ENABLE ROW LEVEL SECURITY;

CREATE POLICY "event_attendees_select" ON public.event_attendees
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_insert" ON public.event_attendees
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_update" ON public.event_attendees
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "event_attendees_delete" ON public.event_attendees
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- AUTOMATIONS MODULE
-- =============================================================================

-- automations
ALTER TABLE public.automations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automations_select" ON public.automations
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automations_insert" ON public.automations
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automations_update" ON public.automations
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automations_delete" ON public.automations
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- automation_actions
ALTER TABLE public.automation_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automation_actions_select" ON public.automation_actions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_insert" ON public.automation_actions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_update" ON public.automation_actions
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_actions_delete" ON public.automation_actions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- automation_runs
ALTER TABLE public.automation_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "automation_runs_select" ON public.automation_runs
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_insert" ON public.automation_runs
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_update" ON public.automation_runs
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "automation_runs_delete" ON public.automation_runs
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- FLEXIBLE DATA MODULE
-- =============================================================================

-- tags
ALTER TABLE public.tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tags_select" ON public.tags
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "tags_insert" ON public.tags
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tags_update" ON public.tags
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "tags_delete" ON public.tags
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- taggings
ALTER TABLE public.taggings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "taggings_select" ON public.taggings
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "taggings_insert" ON public.taggings
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "taggings_update" ON public.taggings
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "taggings_delete" ON public.taggings
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- custom_field_definitions
ALTER TABLE public.custom_field_definitions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "custom_field_definitions_select" ON public.custom_field_definitions
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_insert" ON public.custom_field_definitions
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_update" ON public.custom_field_definitions
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_definitions_delete" ON public.custom_field_definitions
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- custom_field_values
ALTER TABLE public.custom_field_values ENABLE ROW LEVEL SECURITY;

CREATE POLICY "custom_field_values_select" ON public.custom_field_values
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_insert" ON public.custom_field_values
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_update" ON public.custom_field_values
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "custom_field_values_delete" ON public.custom_field_values
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());

-- =============================================================================
-- ACTIVITY MODULE
-- =============================================================================

-- activities
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "activities_select" ON public.activities
  FOR SELECT USING (org_id = public.get_user_org_id());

CREATE POLICY "activities_insert" ON public.activities
  FOR INSERT WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "activities_update" ON public.activities
  FOR UPDATE USING (org_id = public.get_user_org_id())
  WITH CHECK (org_id = public.get_user_org_id());

CREATE POLICY "activities_delete" ON public.activities
  FOR DELETE USING (org_id = public.get_user_org_id() AND public.is_admin());
