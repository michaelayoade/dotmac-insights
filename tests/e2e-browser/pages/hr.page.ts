import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for HR module.
 *
 * Handles:
 * - Employee list and detail
 * - Leave management
 * - Attendance tracking
 * - Payroll
 * - Recruitment
 */
export class HRPage extends BasePage {
  // URL patterns
  readonly dashboardUrl = '/hr';
  readonly employeesUrl = '/hr/employees';
  readonly leaveUrl = '/hr/leave';
  readonly attendanceUrl = '/hr/attendance';
  readonly payrollUrl = '/hr/payroll';
  readonly recruitmentUrl = '/hr/recruitment';
  readonly departmentsUrl = '/hr/departments';

  // Dashboard elements
  readonly dashboardStats: Locator;
  readonly statTotalEmployees: Locator;
  readonly statOnLeave: Locator;
  readonly statPendingApprovals: Locator;

  // Employee list elements
  readonly employeesTable: Locator;
  readonly employeeSearch: Locator;
  readonly departmentFilter: Locator;
  readonly statusFilter: Locator;
  readonly newEmployeeButton: Locator;

  // Employee detail elements
  readonly employeeHeader: Locator;
  readonly employeeStatus: Locator;
  readonly employeeDepartment: Locator;
  readonly employeeDesignation: Locator;

  // Leave elements
  readonly leaveTable: Locator;
  readonly leaveSearch: Locator;
  readonly leaveTypeFilter: Locator;
  readonly leaveStatusFilter: Locator;
  readonly newLeaveButton: Locator;
  readonly approveLeaveButton: Locator;
  readonly rejectLeaveButton: Locator;

  // Leave form elements
  readonly leaveForm: Locator;
  readonly leaveTypeSelect: Locator;
  readonly leaveStartDate: Locator;
  readonly leaveEndDate: Locator;
  readonly leaveReason: Locator;

  // Attendance elements
  readonly attendanceTable: Locator;
  readonly attendanceDate: Locator;
  readonly checkInButton: Locator;
  readonly checkOutButton: Locator;

  // Payroll elements
  readonly payrollTable: Locator;
  readonly payrollPeriodSelect: Locator;
  readonly runPayrollButton: Locator;
  readonly payslipLink: Locator;

  // Recruitment elements
  readonly jobOpeningsTable: Locator;
  readonly applicantsTable: Locator;
  readonly newJobOpeningButton: Locator;

  constructor(page: Page) {
    super(page);

    // Dashboard
    this.dashboardStats = page.locator('.dashboard-stats, [data-testid="hr-stats"]');
    this.statTotalEmployees = page.locator('[data-testid="stat-employees"], .stat-employees');
    this.statOnLeave = page.locator('[data-testid="stat-on-leave"], .stat-on-leave');
    this.statPendingApprovals = page.locator('[data-testid="stat-pending"], .stat-pending');

    // Employees
    this.employeesTable = page.locator('[data-testid="employees-table"]');
    this.employeeSearch = page.locator('[data-testid="employees-search"]');
    this.departmentFilter = page.locator('[data-testid="department-filter-button"]');
    this.statusFilter = page.locator('[data-testid="status-filter-button"]');
    this.newEmployeeButton = page.locator('[data-testid="new-employee-button"]');

    // Employee detail
    this.employeeHeader = page.locator('[data-testid="page-title"]');
    this.employeeStatus = page.locator('[data-testid="employee-status"]');
    this.employeeDepartment = page.locator('[data-testid="employee-department"]');
    this.employeeDesignation = page.locator('[data-testid="employee-designation"]');

    // Leave
    this.leaveTable = page.locator('[data-testid="leave-table"]');
    this.leaveSearch = page.locator('[data-testid="leave-search"]');
    this.leaveTypeFilter = page.locator('[data-testid="leave-type-filter"]');
    this.leaveStatusFilter = page.locator('[data-testid="leave-status-filter-button"]');
    this.newLeaveButton = page.locator('[data-testid="new-leave-button"]');
    this.approveLeaveButton = page.locator('[data-testid="approve-leave"]');
    this.rejectLeaveButton = page.locator('[data-testid="reject-leave"]');

    // Leave form
    this.leaveForm = page.locator('[data-testid="leave-form"]');
    this.leaveTypeSelect = page.locator('select[name="leave_type_id"]');
    this.leaveStartDate = page.locator('input[name="start_date"]');
    this.leaveEndDate = page.locator('input[name="end_date"]');
    this.leaveReason = page.locator('textarea[name="description"]');

    // Attendance
    this.attendanceTable = page.locator('#attendance-table table, [data-testid="attendance-table"]');
    this.attendanceDate = page.locator('input[name="date"], [data-testid="attendance-date"]');
    this.checkInButton = page.locator('button:has-text("Check In"), [data-testid="check-in"]');
    this.checkOutButton = page.locator('button:has-text("Check Out"), [data-testid="check-out"]');

    // Payroll
    this.payrollTable = page.locator('#payroll-table table, [data-testid="payroll-table"]');
    this.payrollPeriodSelect = page.locator('select[name="period"], [data-testid="payroll-period"]');
    this.runPayrollButton = page.locator('button:has-text("Run Payroll"), [data-testid="run-payroll"]');
    this.payslipLink = page.locator('a:has-text("Payslip"), a:has-text("View Slip")');

    // Recruitment
    this.jobOpeningsTable = page.locator('#job-openings-table table, [data-testid="job-openings-table"]');
    this.applicantsTable = page.locator('#applicants-table table, [data-testid="applicants-table"]');
    this.newJobOpeningButton = page.locator('[data-testid="new-job-opening"], a[href*="/recruitment/new"], button:has-text("New Opening")');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async gotoDashboard(): Promise<void> {
    await this.goto(this.dashboardUrl);
  }

  async gotoEmployees(): Promise<void> {
    await this.goto(this.employeesUrl);
  }

  async gotoEmployee(id: number): Promise<void> {
    await this.goto(`${this.employeesUrl}/${id}`);
  }

  async gotoLeave(): Promise<void> {
    await this.goto(this.leaveUrl);
  }

  async gotoLeaveApplications(): Promise<void> {
    await this.goto(`${this.leaveUrl}/applications`);
  }

  async gotoAttendance(): Promise<void> {
    await this.goto(this.attendanceUrl);
  }

  async gotoPayroll(): Promise<void> {
    await this.goto(this.payrollUrl);
  }

  async gotoRecruitment(): Promise<void> {
    await this.goto(this.recruitmentUrl);
  }

  async gotoDepartments(): Promise<void> {
    await this.goto(this.departmentsUrl);
  }

  // =========================================================================
  // EMPLOYEES
  // =========================================================================

  async searchEmployees(query: string): Promise<void> {
    await this.employeeSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterByDepartment(department: string): Promise<void> {
    const select = this.page.locator('select[name="department"], [data-testid="department-filter"]');
    if (await select.count() > 0) {
      await select.selectOption(department);
      await this.waitForHtmxComplete();
      return;
    }

    await this.departmentFilter.click();
    const option = this.page.locator(`[data-testid="department-option-${department.replace(/\\s+/g, '-')}"]`);
    await option.click();
    await this.waitForHtmxComplete();
  }

  async filterByStatus(status: 'active' | 'inactive' | 'onboarding'): Promise<void> {
    const select = this.page.locator('select[name="status"], [data-testid="status-filter"]');
    if (await select.count() > 0) {
      await select.selectOption(status);
      await this.waitForHtmxComplete();
      return;
    }

    await this.statusFilter.click();
    const option = this.page.locator(`[data-testid="status-option-${status.replace(/\\s+/g, '-')}"]`);
    await option.click();
    await this.waitForHtmxComplete();
  }

  async getEmployeeCount(): Promise<number> {
    return await this.getTableRowCount(this.employeesTable);
  }

  async hasEmployees(): Promise<boolean> {
    return (await this.employeesTable.locator('tbody tr').count()) > 0;
  }

  async clickEmployee(name: string): Promise<void> {
    let link = this.employeesTable.locator('a[data-testid^="employee-name-"]', { hasText: name }).first();
    if (await link.count() === 0) {
      const row = this.employeesTable.locator(`tbody tr:has-text("${name}")`).first();
      link = row.locator('a').first();
    }
    if (await link.count() === 0) {
      link = this.employeesTable.locator('tbody tr a').first();
    }
    const href = await link.getAttribute('href');
    if (href) {
      const navPromise = this.page.waitForURL(/\\/employees\\/\\d+/, { timeout: 10000 }).catch(() => null);
      await link.click();
      await navPromise;
      return;
    }
    await this.htmxClick(link);
  }

  async getEmployeeRowData(index: number): Promise<{
    name: string;
    department: string;
    designation: string;
    status: string;
  }> {
    const row = this.employeesTable.locator('tbody tr').nth(index);
    const nameCell = row.locator('[data-testid^="employee-name-"]').first();
    return {
      name: (await nameCell.textContent()) || (await row.locator('td').nth(0).textContent()) || '',
      department: await row.locator('td').nth(1).textContent() || '',
      designation: await row.locator('td').nth(2).textContent() || '',
      status: await row.locator('[data-status]').textContent() || '',
    };
  }

  // =========================================================================
  // LEAVE
  // =========================================================================

  async searchLeave(query: string): Promise<void> {
    await this.leaveSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterLeaveByType(type: string): Promise<void> {
    await this.leaveTypeFilter.selectOption(type);
    await this.waitForHtmxComplete();
  }

  async filterLeaveByStatus(status: 'pending' | 'approved' | 'rejected'): Promise<void> {
    const normalizedStatus = status === 'pending' ? 'open' : status;
    const option = this.page.locator(
      `[data-testid="leave-status-option-${normalizedStatus.replace(/\\s+/g, '-')}"]`,
    );
    if (await option.count() > 0) {
      await this.leaveStatusFilter.click();
      await option.click();
      await this.waitForHtmxComplete();
      return;
    }

    const select = this.page.locator('select[name="status"], [data-testid="leave-status-filter"]');
    if (await select.count() > 0) {
      await select.selectOption(normalizedStatus);
      await this.waitForHtmxComplete();
      return;
    }
    await this.waitForHtmxComplete();
  }

  async getLeaveCount(): Promise<number> {
    return await this.getTableRowCount(this.leaveTable);
  }

  async hasLeaveApplications(): Promise<boolean> {
    return (await this.leaveTable.locator('tbody tr').count()) > 0;
  }

  async applyLeave(data: {
    type: string;
    startDate: string;
    endDate: string;
    reason: string;
  }): Promise<void> {
    await this.newLeaveButton.click();
    await this.waitForHtmxComplete();

    await this.leaveTypeSelect.selectOption(data.type);
    await this.leaveStartDate.fill(data.startDate);
    await this.leaveEndDate.fill(data.endDate);
    await this.leaveReason.fill(data.reason);

    await this.htmxSubmitForm(this.leaveForm);
  }

  async approveLeave(): Promise<void> {
    const navPromise = this.page.waitForURL(/\\/hr\\/leave\\/\\d+/, { timeout: 10000 }).catch(() => null);
    await this.htmxClick(this.approveLeaveButton);
    await navPromise;
  }

  async rejectLeave(): Promise<void> {
    const navPromise = this.page.waitForURL(/\\/hr\\/leave\\/\\d+/, { timeout: 10000 }).catch(() => null);
    await this.htmxClick(this.rejectLeaveButton);
    await navPromise;
  }

  // =========================================================================
  // ATTENDANCE
  // =========================================================================

  async getAttendanceCount(): Promise<number> {
    return await this.getTableRowCount(this.attendanceTable);
  }

  async hasAttendanceRecords(): Promise<boolean> {
    return (await this.attendanceTable.locator('tbody tr').count()) > 0;
  }

  async checkIn(): Promise<void> {
    await this.htmxClick(this.checkInButton);
  }

  async checkOut(): Promise<void> {
    await this.htmxClick(this.checkOutButton);
  }

  // =========================================================================
  // PAYROLL
  // =========================================================================

  async getPayrollCount(): Promise<number> {
    return await this.getTableRowCount(this.payrollTable);
  }

  async hasPayrollRecords(): Promise<boolean> {
    return (await this.payrollTable.locator('tbody tr').count()) > 0;
  }

  async selectPayrollPeriod(period: string): Promise<void> {
    await this.payrollPeriodSelect.selectOption(period);
    await this.waitForHtmxComplete();
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectEmployeeStatus(status: string): Promise<void> {
    await expect(this.employeeStatus.first()).toContainText(status, { ignoreCase: true });
  }

  async expectEmployeeInList(name: string): Promise<void> {
    const row = this.employeesTable.locator(`tbody tr:has-text("${name}")`);
    await expect(row).toBeVisible();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('[data-testid="employees-empty-state"], [data-testid="leave-empty-state"]');
    await expect(emptyState).toBeVisible();
  }

  async expectStatsVisible(): Promise<void> {
    await expect(this.dashboardStats.first()).toBeVisible();
  }
}
