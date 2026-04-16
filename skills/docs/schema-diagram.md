# Schema Diagram

Full ER diagram of the Skene Skills schema, grouped by skill.

```mermaid
erDiagram
    %% =========================================
    %% IDENTITY
    %% =========================================

    organizations {
        uuid id PK
        text name
        text slug UK
        text domain
        text stripe_customer_id
        jsonb metadata
    }

    users {
        uuid id PK
        uuid org_id FK
        uuid auth_id UK
        text email
        text full_name
        boolean is_active
    }

    teams {
        uuid id PK
        uuid org_id FK
        text name
    }

    memberships {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        uuid team_id FK
        membership_role role
        membership_status status
    }

    roles {
        uuid id PK
        uuid org_id FK
        text name
    }

    permissions {
        uuid id PK
        uuid org_id FK
        uuid role_id FK
        text resource
        text action
    }

    organizations ||--o{ users : "has"
    organizations ||--o{ teams : "has"
    organizations ||--o{ memberships : "has"
    users ||--o{ memberships : "belongs to"
    teams ||--o{ memberships : "groups"
    organizations ||--o{ roles : "defines"
    roles ||--o{ permissions : "grants"

    %% =========================================
    %% CRM
    %% =========================================

    contacts {
        uuid id PK
        uuid org_id FK
        uuid owner_id FK
        text first_name
        text last_name
        text email
        contact_type type
        text source
    }

    companies {
        uuid id PK
        uuid org_id FK
        uuid owner_id FK
        text name
        text domain
        text industry
        numeric annual_revenue
    }

    contact_companies {
        uuid id PK
        uuid org_id FK
        uuid contact_id FK
        uuid company_id FK
        text title
        boolean is_primary
    }

    organizations ||--o{ contacts : "has"
    organizations ||--o{ companies : "has"
    users ||--o{ contacts : "owns"
    users ||--o{ companies : "owns"
    contacts ||--o{ contact_companies : "works at"
    companies ||--o{ contact_companies : "employs"

    %% =========================================
    %% PIPELINE
    %% =========================================

    pipelines {
        uuid id PK
        uuid org_id FK
        text name
        boolean is_default
    }

    pipeline_stages {
        uuid id PK
        uuid org_id FK
        uuid pipeline_id FK
        text name
        integer position
        boolean is_terminal
    }

    deals {
        uuid id PK
        uuid org_id FK
        uuid pipeline_id FK
        uuid stage_id FK
        uuid owner_id FK
        uuid contact_id FK
        uuid company_id FK
        text title
        numeric value
        deal_status status
    }

    deal_stage_history {
        uuid id PK
        uuid org_id FK
        uuid deal_id FK
        uuid from_stage_id FK
        uuid to_stage_id FK
        uuid changed_by FK
        integer duration_seconds
    }

    organizations ||--o{ pipelines : "has"
    pipelines ||--o{ pipeline_stages : "contains"
    pipelines ||--o{ deals : "tracks"
    pipeline_stages ||--o{ deals : "current stage"
    deals ||--o{ deal_stage_history : "history"
    contacts ||--o{ deals : "associated"
    companies ||--o{ deals : "associated"
    users ||--o{ deals : "owns"

    %% =========================================
    %% TASKS
    %% =========================================

    projects {
        uuid id PK
        uuid org_id FK
        uuid owner_id FK
        text name
        task_status status
        task_priority priority
    }

    tasks {
        uuid id PK
        uuid org_id FK
        uuid project_id FK
        uuid assignee_id FK
        uuid creator_id FK
        text title
        task_status status
        task_priority priority
    }

    task_dependencies {
        uuid id PK
        uuid org_id FK
        uuid task_id FK
        uuid depends_on_id FK
    }

    organizations ||--o{ projects : "has"
    projects ||--o{ tasks : "contains"
    users ||--o{ tasks : "assigned to"
    tasks ||--o{ task_dependencies : "blocked by"

    %% =========================================
    %% SUPPORT
    %% =========================================

    tickets {
        uuid id PK
        uuid org_id FK
        uuid contact_id FK
        uuid assignee_id FK
        text title
        ticket_status status
        ticket_priority priority
        channel_type channel
    }

    organizations ||--o{ tickets : "has"
    contacts ||--o{ tickets : "submitted"
    users ||--o{ tickets : "assigned to"

    %% =========================================
    %% COMMS
    %% =========================================

    threads {
        uuid id PK
        uuid org_id FK
        text entity_type
        uuid entity_id
        text subject
        channel_type channel
    }

    messages {
        uuid id PK
        uuid org_id FK
        uuid thread_id FK
        uuid author_id FK
        uuid contact_id FK
        message_direction direction
        text body
    }

    organizations ||--o{ threads : "has"
    threads ||--o{ messages : "contains"
    users ||--o{ messages : "authored"
    contacts ||--o{ messages : "sent"

    %% =========================================
    %% CONTENT
    %% =========================================

    folders {
        uuid id PK
        uuid org_id FK
        uuid parent_id FK
        text name
    }

    documents {
        uuid id PK
        uuid org_id FK
        uuid folder_id FK
        uuid author_id FK
        text title
        document_status status
    }

    comments {
        uuid id PK
        uuid org_id FK
        uuid author_id FK
        text entity_type
        uuid entity_id
        text body
        uuid parent_id FK
    }

    organizations ||--o{ folders : "has"
    folders ||--o{ folders : "parent"
    folders ||--o{ documents : "contains"
    users ||--o{ documents : "authored"
    users ||--o{ comments : "authored"

    %% =========================================
    %% BILLING
    %% =========================================

    products {
        uuid id PK
        uuid org_id FK
        text name
        boolean is_active
        text stripe_product_id
    }

    prices {
        uuid id PK
        uuid org_id FK
        uuid product_id FK
        numeric amount
        text currency
        billing_interval interval
    }

    subscriptions {
        uuid id PK
        uuid org_id FK
        uuid contact_id FK
        uuid company_id FK
        uuid price_id FK
        subscription_status status
        integer quantity
    }

    invoices {
        uuid id PK
        uuid org_id FK
        uuid subscription_id FK
        text number
        invoice_status status
        numeric total
        numeric amount_due
    }

    payments {
        uuid id PK
        uuid org_id FK
        uuid invoice_id FK
        numeric amount
        payment_status status
        text stripe_payment_intent_id
    }

    organizations ||--o{ products : "sells"
    products ||--o{ prices : "priced at"
    prices ||--o{ subscriptions : "subscribed"
    contacts ||--o{ subscriptions : "subscribes"
    companies ||--o{ subscriptions : "subscribes"
    subscriptions ||--o{ invoices : "billed"
    invoices ||--o{ payments : "paid by"

    %% =========================================
    %% CALENDAR
    %% =========================================

    events {
        uuid id PK
        uuid org_id FK
        uuid creator_id FK
        text entity_type
        uuid entity_id
        text title
        timestamptz starts_at
        timestamptz ends_at
    }

    event_attendees {
        uuid id PK
        uuid org_id FK
        uuid event_id FK
        uuid user_id FK
        uuid contact_id FK
        attendee_response response
    }

    organizations ||--o{ events : "has"
    events ||--o{ event_attendees : "attended by"
    users ||--o{ event_attendees : "attends"
    contacts ||--o{ event_attendees : "attends"

    %% =========================================
    %% AUTOMATIONS
    %% =========================================

    automations {
        uuid id PK
        uuid org_id FK
        text name
        automation_trigger_type trigger_type
        automation_status status
    }

    automation_actions {
        uuid id PK
        uuid org_id FK
        uuid automation_id FK
        text action_type
        integer position
    }

    automation_runs {
        uuid id PK
        uuid org_id FK
        uuid automation_id FK
        run_status status
        timestamptz started_at
    }

    organizations ||--o{ automations : "has"
    automations ||--o{ automation_actions : "executes"
    automations ||--o{ automation_runs : "ran"

    %% =========================================
    %% ANALYTICS
    %% =========================================

    tags {
        uuid id PK
        uuid org_id FK
        text name
        text color
    }

    taggings {
        uuid id PK
        uuid org_id FK
        uuid tag_id FK
        text entity_type
        uuid entity_id
    }

    custom_field_definitions {
        uuid id PK
        uuid org_id FK
        text entity_type
        text name
        field_type field_type
    }

    custom_field_values {
        uuid id PK
        uuid org_id FK
        uuid field_id FK
        text entity_type
        uuid entity_id
    }

    activities {
        uuid id PK
        uuid org_id FK
        uuid actor_id FK
        text entity_type
        uuid entity_id
        activity_action action
        jsonb changes
    }

    organizations ||--o{ tags : "has"
    tags ||--o{ taggings : "applied"
    organizations ||--o{ custom_field_definitions : "defines"
    custom_field_definitions ||--o{ custom_field_values : "values"
    organizations ||--o{ activities : "has"
    users ||--o{ activities : "performed"

    %% =========================================
    %% FORMS
    %% =========================================

    form_definitions {
        uuid id PK
        uuid org_id FK
        uuid creator_id FK
        text name
        text slug UK
        form_status status
    }

    form_fields {
        uuid id PK
        uuid org_id FK
        uuid form_id FK
        text label
        text field_key
        form_field_type field_type
        integer position
    }

    form_submissions {
        uuid id PK
        uuid org_id FK
        uuid form_id FK
        jsonb data
        timestamptz submitted_at
    }

    form_uploads {
        uuid id PK
        uuid org_id FK
        uuid submission_id FK
        text file_name
        text storage_path
    }

    organizations ||--o{ form_definitions : "has"
    form_definitions ||--o{ form_fields : "contains"
    form_definitions ||--o{ form_submissions : "receives"
    form_submissions ||--o{ form_uploads : "attaches"

    %% =========================================
    %% NOTIFICATIONS
    %% =========================================

    notification_templates {
        uuid id PK
        uuid org_id FK
        text name
        text slug UK
        notification_channel channel
    }

    notification_deliveries {
        uuid id PK
        uuid org_id FK
        uuid template_id FK
        uuid user_id FK
        delivery_status status
    }

    notification_preferences {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        notification_channel channel
        boolean is_enabled
    }

    push_tokens {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        text token
        push_platform platform
    }

    organizations ||--o{ notification_templates : "has"
    notification_templates ||--o{ notification_deliveries : "sent"
    users ||--o{ notification_deliveries : "receives"
    users ||--o{ notification_preferences : "configures"
    users ||--o{ push_tokens : "registers"

    %% =========================================
    %% CAMPAIGNS
    %% =========================================

    campaigns {
        uuid id PK
        uuid org_id FK
        uuid creator_id FK
        text name
        campaign_status status
    }

    campaign_segments {
        uuid id PK
        uuid org_id FK
        text name
        jsonb filter_rules
    }

    campaign_lists {
        uuid id PK
        uuid org_id FK
        uuid campaign_id FK
        uuid contact_id FK
    }

    campaign_sends {
        uuid id PK
        uuid org_id FK
        uuid campaign_id FK
        uuid contact_id FK
        send_status status
    }

    campaign_events {
        uuid id PK
        uuid org_id FK
        uuid send_id FK
        campaign_event_type event_type
    }

    organizations ||--o{ campaigns : "has"
    organizations ||--o{ campaign_segments : "defines"
    campaigns ||--o{ campaign_lists : "targets"
    contacts ||--o{ campaign_lists : "listed"
    campaigns ||--o{ campaign_sends : "sends"
    campaign_sends ||--o{ campaign_events : "tracks"

    %% =========================================
    %% COMMERCE
    %% =========================================

    orders {
        uuid id PK
        uuid org_id FK
        uuid contact_id FK
        text number
        order_status status
        numeric total
    }

    order_items {
        uuid id PK
        uuid org_id FK
        uuid order_id FK
        uuid product_id FK
        integer quantity
        numeric unit_price
    }

    carts {
        uuid id PK
        uuid org_id FK
        uuid contact_id FK
        cart_status status
    }

    cart_items {
        uuid id PK
        uuid org_id FK
        uuid cart_id FK
        uuid product_id FK
        integer quantity
    }

    shipping_records {
        uuid id PK
        uuid org_id FK
        uuid order_id FK
        text carrier
        shipping_status status
    }

    fulfillments {
        uuid id PK
        uuid org_id FK
        uuid order_id FK
        fulfillment_status status
        uuid fulfilled_by FK
    }

    organizations ||--o{ orders : "has"
    orders ||--o{ order_items : "contains"
    orders ||--o{ shipping_records : "ships"
    orders ||--o{ fulfillments : "fulfills"
    organizations ||--o{ carts : "has"
    carts ||--o{ cart_items : "contains"
    contacts ||--o{ orders : "places"
    products ||--o{ order_items : "ordered"

    %% =========================================
    %% KNOWLEDGE
    %% =========================================

    articles {
        uuid id PK
        uuid org_id FK
        uuid author_id FK
        text title
        text slug UK
        article_status status
    }

    article_categories {
        uuid id PK
        uuid org_id FK
        text name
        text slug UK
        uuid parent_id FK
    }

    article_category_links {
        uuid id PK
        uuid org_id FK
        uuid article_id FK
        uuid category_id FK
    }

    organizations ||--o{ articles : "has"
    users ||--o{ articles : "authored"
    organizations ||--o{ article_categories : "defines"
    article_categories ||--o{ article_categories : "parent"
    articles ||--o{ article_category_links : "categorized"
    article_categories ||--o{ article_category_links : "contains"

    %% =========================================
    %% APPROVALS
    %% =========================================

    approval_chains {
        uuid id PK
        uuid org_id FK
        text name
        text entity_type
        boolean is_active
    }

    approval_steps {
        uuid id PK
        uuid org_id FK
        uuid chain_id FK
        integer position
        uuid approver_id FK
    }

    approval_requests {
        uuid id PK
        uuid org_id FK
        uuid chain_id FK
        text entity_type
        uuid entity_id
        approval_status status
    }

    approval_decisions {
        uuid id PK
        uuid org_id FK
        uuid request_id FK
        uuid decided_by FK
        approval_decision decision
    }

    approval_delegations {
        uuid id PK
        uuid org_id FK
        uuid delegator_id FK
        uuid delegate_id FK
        boolean is_active
    }

    organizations ||--o{ approval_chains : "has"
    approval_chains ||--o{ approval_steps : "contains"
    approval_chains ||--o{ approval_requests : "receives"
    approval_requests ||--o{ approval_decisions : "decided"
    users ||--o{ approval_delegations : "delegates"

    %% =========================================
    %% INTEGRATIONS
    %% =========================================

    connected_apps {
        uuid id PK
        uuid org_id FK
        text name
        text provider
        integration_status status
    }

    oauth_tokens {
        uuid id PK
        uuid org_id FK
        uuid app_id FK
        uuid user_id FK
        text access_token_enc
    }

    webhooks {
        uuid id PK
        uuid org_id FK
        text url
        boolean is_active
    }

    webhook_events {
        uuid id PK
        uuid org_id FK
        uuid webhook_id FK
        text event_type
        webhook_event_status status
    }

    sync_logs {
        uuid id PK
        uuid org_id FK
        uuid app_id FK
        sync_direction direction
        sync_status status
    }

    organizations ||--o{ connected_apps : "has"
    connected_apps ||--o{ oauth_tokens : "authenticates"
    connected_apps ||--o{ sync_logs : "syncs"
    organizations ||--o{ webhooks : "registers"
    webhooks ||--o{ webhook_events : "fires"

    %% =========================================
    %% COMPLIANCE
    %% =========================================

    consent_records {
        uuid id PK
        uuid org_id FK
        text entity_type
        uuid entity_id
        text purpose
        text legal_basis
    }

    deletion_requests {
        uuid id PK
        uuid org_id FK
        text requester_type
        uuid requester_id
        deletion_status status
    }

    retention_policies {
        uuid id PK
        uuid org_id FK
        text entity_type
        integer retention_days
        retention_action action
    }

    organizations ||--o{ consent_records : "tracks"
    organizations ||--o{ deletion_requests : "receives"
    organizations ||--o{ retention_policies : "defines"
```
