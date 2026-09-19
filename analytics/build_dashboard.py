#!/usr/bin/env python3
"""Build the interactive WhichCloud cost dashboard for Amazon Quick (QuickSight).

Interactivity: Workload + Tier dropdown filters, and click-to-filter on every
bar chart (click a bar -> all visuals filter to it; click again to clear).

  python3 build_dashboard.py            # for update-analysis / update-dashboard
  python3 build_dashboard.py --create   # adds permissions, for first create
"""
import json
import sys

ACCOUNT = "616551057703"
REGION = "ap-south-1"
USER = f"arn:aws:quicksight:{REGION}:{ACCOUNT}:user/default/{ACCOUNT}"
DS_ARN = f"arn:aws:quicksight:{REGION}:{ACCOUNT}:dataset/whichcloud-costs"
DSI = "costs"
TIER_COLORS = {"1 Cheapest": "#2E7D32", "2 Balanced": "#1E88E5", "3 Grow-into": "#F57C00"}


def col(name):
    return {"DataSetIdentifier": DSI, "ColumnName": name}


def dim(fid, name):
    return {"CategoricalDimensionField": {"FieldId": fid, "Column": col(name)}}


def usd(decimals, scale="NONE"):
    return {"FormatConfiguration": {"CurrencyDisplayFormatConfiguration": {
        "Symbol": "USD", "NumberScale": scale,
        "DecimalPlacesConfiguration": {"DecimalPlaces": decimals}}}}


def cost_sum(fid, fmt=None):
    return {"NumericalMeasureField": {
        "FieldId": fid, "Column": col("monthly_cost"),
        "AggregationFunction": {"SimpleNumericalAggregation": "SUM"},
        "FormatConfiguration": fmt or usd(0)}}


def title(text):
    return {"Visibility": "VISIBLE", "FormatText": {"PlainText": text}}


def click_filter(action_id):
    return [{"CustomActionId": action_id, "Name": "Click to filter dashboard",
             "Status": "ENABLED", "Trigger": "DATA_POINT_CLICK",
             "ActionOperations": [{"FilterOperation": {
                 "SelectedFieldsConfiguration": {"SelectedFieldOptions": "ALL_FIELDS"},
                 "TargetVisualsConfiguration": {"SameSheetTargetVisualConfiguration": {
                     "TargetVisualOptions": "ALL_VISUALS"}}}}]}]


def tier_palette(fid):
    return {"ColorMap": [{"Element": {"FieldId": fid, "FieldValue": v}, "Color": c}
                         for v, c in TIER_COLORS.items()]}


AXIS_FMT = usd(1, "AUTO")  # $1.5K instead of repeated $1K/$2K ticks

visuals = [
    {"KPIVisual": {
        "VisualId": "kpi_total", "Title": title("Total monthly cost (13 workloads x 3 tiers)"),
        "ChartConfiguration": {"FieldWells": {"Values": [cost_sum("k1")]}}}},
    {"KPIVisual": {
        "VisualId": "kpi_items", "Title": title("Priced line items"),
        "ChartConfiguration": {"FieldWells": {"Values": [{"CategoricalMeasureField": {
            "FieldId": "k2", "Column": col("sku"), "AggregationFunction": "COUNT"}}]}}}},
    {"KPIVisual": {
        "VisualId": "kpi_free", "Title": title("Free / included line items ($0)"),
        "ChartConfiguration": {"FieldWells": {"Values": [{"NumericalMeasureField": {
            "FieldId": "k3", "Column": col("is_free"),
            "AggregationFunction": {"SimpleNumericalAggregation": "SUM"}}}]}}}},
    {"BarChartVisual": {
        "VisualId": "bar_workload_tier",
        "Title": title("Monthly cost by workload and architecture tier (click a bar to filter)"),
        "ChartConfiguration": {
            "FieldWells": {"BarChartAggregatedFieldWells": {
                "Category": [dim("b1", "workload")], "Values": [cost_sum("b2", AXIS_FMT)],
                "Colors": [dim("b3", "tier")]}},
            "Orientation": "HORIZONTAL", "BarsArrangement": "CLUSTERED",
            "SortConfiguration": {
                "CategorySort": [{"FieldSort": {"FieldId": "b2", "Direction": "DESC"}}],
                "ColorSort": [{"FieldSort": {"FieldId": "b3", "Direction": "ASC"}}]},
            "VisualPalette": tier_palette("b3")},
        "Actions": click_filter("act_workload")}},
    {"BarChartVisual": {
        "VisualId": "bar_tier", "Title": title("Cost of reliability: total by tier (click to filter)"),
        "ChartConfiguration": {
            "FieldWells": {"BarChartAggregatedFieldWells": {
                "Category": [dim("t1", "tier")], "Values": [cost_sum("t2", AXIS_FMT)]}},
            "Orientation": "VERTICAL",
            "SortConfiguration": {"CategorySort": [{"FieldSort": {"FieldId": "t1", "Direction": "ASC"}}]},
            "VisualPalette": tier_palette("t1")},
        "Actions": click_filter("act_tier")}},
    {"BarChartVisual": {
        "VisualId": "bar_drivers", "Title": title("Top 10 cost drivers by service family (click to filter)"),
        "ChartConfiguration": {
            "FieldWells": {"BarChartAggregatedFieldWells": {
                "Category": [dim("d1", "service_family")], "Values": [cost_sum("d2", AXIS_FMT)]}},
            "Orientation": "HORIZONTAL",
            "SortConfiguration": {
                "CategorySort": [{"FieldSort": {"FieldId": "d2", "Direction": "DESC"}}],
                "CategoryItemsLimit": {"ItemsLimit": 10, "OtherCategories": "EXCLUDE"}}},
        "Actions": click_filter("act_drivers")}},
    {"TableVisual": {
        "VisualId": "tbl", "Title": title("Workload cost detail"),
        "ChartConfiguration": {
            "FieldWells": {"TableAggregatedFieldWells": {
                "GroupBy": [dim("r1", "workload"), dim("r2", "tier")], "Values": [cost_sum("r3")]}},
            "SortConfiguration": {"RowSort": [{"FieldSort": {"FieldId": "r3", "Direction": "DESC"}}]}}}},
]


def cell(eid, etype, c, r, cs, rs):
    return {"ElementId": eid, "ElementType": etype, "ColumnIndex": c,
            "RowIndex": r, "ColumnSpan": cs, "RowSpan": rs}


layout = [
    cell("fc_workload", "FILTER_CONTROL", 0, 0, 12, 3),
    cell("fc_tier", "FILTER_CONTROL", 0, 3, 12, 3),
    cell("kpi_total", "VISUAL", 12, 0, 8, 6),
    cell("kpi_items", "VISUAL", 20, 0, 8, 6),
    cell("kpi_free", "VISUAL", 28, 0, 8, 6),
    cell("bar_workload_tier", "VISUAL", 0, 6, 22, 14),
    cell("bar_tier", "VISUAL", 22, 6, 14, 14),
    cell("bar_drivers", "VISUAL", 0, 20, 18, 12),
    cell("tbl", "VISUAL", 18, 20, 18, 12),
]


def list_filter(fid, column):
    return {"CategoryFilter": {"FilterId": fid, "Column": col(column), "Configuration": {
        "FilterListConfiguration": {"MatchOperator": "CONTAINS", "SelectAllOptions": "FILTER_ALL_VALUES"}}}}


def filter_group(gid, filt):
    return {"FilterGroupId": gid, "CrossDataset": "SINGLE_DATASET", "Status": "ENABLED",
            "Filters": [filt],
            "ScopeConfiguration": {"SelectedSheets": {"SheetVisualScopingConfigurations": [
                {"SheetId": "overview", "Scope": "ALL_VISUALS"}]}}}


definition = {
    "DataSetIdentifierDeclarations": [{"Identifier": DSI, "DataSetArn": DS_ARN}],
    "CalculatedFields": [
        {"DataSetIdentifier": DSI, "Name": "service_family", "Expression": "split({sku}, ':', 1)"},
        {"DataSetIdentifier": DSI, "Name": "is_free", "Expression": "ifelse({monthly_cost} = 0, 1, 0)"},
    ],
    "Sheets": [{
        "SheetId": "overview", "Name": "WhichCloud Cost Analytics",
        "Visuals": visuals,
        "FilterControls": [
            {"Dropdown": {"FilterControlId": "fc_workload", "Title": "Workload",
                          "SourceFilterId": "f_workload", "Type": "MULTI_SELECT"}},
            {"Dropdown": {"FilterControlId": "fc_tier", "Title": "Architecture tier",
                          "SourceFilterId": "f_tier", "Type": "MULTI_SELECT"}},
        ],
        "Layouts": [{"Configuration": {"GridLayout": {"Elements": layout}}}],
    }],
    "FilterGroups": [
        filter_group("fg_workload", list_filter("f_workload", "workload")),
        filter_group("fg_tier", list_filter("f_tier", "tier")),
    ],
}

analysis = {"AwsAccountId": ACCOUNT, "AnalysisId": "whichcloud-cost-analysis",
            "Name": "WhichCloud Cost Analytics", "Definition": definition}
dashboard = {"AwsAccountId": ACCOUNT, "DashboardId": "whichcloud-cost-dashboard",
             "Name": "WhichCloud Cost Analytics", "Definition": definition,
             "DashboardPublishOptions": {"AdHocFilteringOption": {"AvailabilityStatus": "ENABLED"}}}

if "--create" in sys.argv:
    analysis["Permissions"] = [{"Principal": USER, "Actions": [
        "quicksight:RestoreAnalysis", "quicksight:UpdateAnalysisPermissions",
        "quicksight:DeleteAnalysis", "quicksight:DescribeAnalysisPermissions",
        "quicksight:QueryAnalysis", "quicksight:DescribeAnalysis", "quicksight:UpdateAnalysis"]}]
    dashboard["Permissions"] = [{"Principal": USER, "Actions": [
        "quicksight:DescribeDashboard", "quicksight:ListDashboardVersions",
        "quicksight:UpdateDashboardPermissions", "quicksight:QueryDashboard",
        "quicksight:UpdateDashboard", "quicksight:DeleteDashboard",
        "quicksight:DescribeDashboardPermissions", "quicksight:UpdateDashboardPublishedVersion"]}]

json.dump(analysis, open("analysis.json", "w"), indent=1)
json.dump(dashboard, open("dashboard.json", "w"), indent=1)
print("wrote analysis.json, dashboard.json")
