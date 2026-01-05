import { test, expect } from '../fixtures/htmx.fixture';
import { ContactsPage } from '../pages/contacts.page';

/**
 * E2E Browser Tests for Contacts Module.
 *
 * Tests the HTMX-powered contact management interface including:
 * - List view with search and filters
 * - Contact creation and editing
 * - Bulk operations
 * - Detail view navigation
 */

test.describe('Contacts List', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
    await contactsPage.gotoList();
  });

  test('displays contacts table @smoke', async () => {
    if (!(await contactsPage.ensureHasContacts())) {
      const emptyState = contactsPage.page.locator('[data-testid="contacts-empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toBeVisible();
        return;
      }
    }
    await expect(contactsPage.contactsTable).toBeVisible();
  });

  test('search filters contacts via HTMX @critical', async ({ htmx }) => {
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    // Get initial count
    const initialCount = await contactsPage.getContactCount();

    // Search for specific contact
    await contactsPage.searchContacts('John');
    await htmx.waitForHtmxIdle();

    // Verify filtered results
    const filteredCount = await contactsPage.getContactCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);

    // Clear search
    await contactsPage.clearSearch();
    await htmx.waitForHtmxIdle();

    // Verify full list restored
    const restoredCount = await contactsPage.getContactCount();
    expect(restoredCount).toBe(initialCount);
  });

  test('filter by contact type updates table', async ({ htmx }) => {
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    await contactsPage.filterByType('customer');
    await htmx.waitForHtmxIdle();

    // All visible rows should have customer type
    const rows = await contactsPage.contactsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      const typeCell = row.locator('[data-testid="contact-type"]');
      await expect(typeCell).toContainText(/customer/i);
    }
  });

  test('filter by status shows only matching contacts', async ({ htmx }) => {
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    await contactsPage.filterByStatus('active');
    await htmx.waitForHtmxIdle();

    // Verify status filter applied
    const rows = await contactsPage.contactsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      const statusBadge = row.locator('[data-testid="contact-status"]');
      await expect(statusBadge).toContainText(/active/i);
    }
  });

  test('pagination loads next page via HTMX', async ({ htmx, page }) => {
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    // Skip if no pagination
    const pagination = contactsPage.getPagination();
    if (await pagination.count() === 0) {
      test.skip();
      return;
    }

    // Get first row content
    const firstRow = await contactsPage.getContactData(0);

    // Go to next page
    await contactsPage.goToNextPage();
    await htmx.waitForHtmxIdle();

    // Verify different content
    const newFirstRow = await contactsPage.getContactData(0);
    expect(newFirstRow.name).not.toBe(firstRow.name);
  });

  test('click contact navigates to detail', async ({ htmx, page }) => {
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    // Get first contact name
    const firstRow = await contactsPage.getContactData(0);

    // Click to view
    await contactsPage.clickContact(firstRow.name);

    // Verify on detail page
    await expect(page).toHaveURL(/\/crm\/contacts\/\d+/);
    await contactsPage.expectContactName(firstRow.name);
  });
});

test.describe('Contact Creation', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
  });

  test('create new contact @critical', async ({ htmx, page }) => {
    const testContact = {
      name: `Test Contact ${Date.now()}`,
      email: `test${Date.now()}@example.com`,
      phone: '+2347012345678',
      type: 'lead',
      category: 'business',
    };

    await contactsPage.createContact(testContact);
    await htmx.waitForHtmxIdle();

    // Verify redirect to detail or list
    await expect(page).toHaveURL(/\/crm\/contacts/);

    // Verify success message
    await contactsPage.expectSuccessToast(/created|saved/i);
  });

  test('validation errors shown on invalid input', async ({ htmx }) => {
    await contactsPage.gotoCreate();

    // Submit empty form
    await contactsPage.htmxSubmitForm(contactsPage.contactForm);

    // Expect validation errors
    await contactsPage.expectFormError('name');
  });

  test('cancel returns to list', async ({ page }) => {
    await contactsPage.gotoCreate();
    await contactsPage.cancelButton.click();

    await expect(page).toHaveURL(contactsPage.listUrl);
  });
});

test.describe('Contact Editing', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
    // Navigate to first contact
    await contactsPage.gotoList();
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
    const firstRow = await contactsPage.getContactData(0);
    await contactsPage.clickContact(firstRow.name);
  });

  test('edit contact updates details', async ({ htmx }) => {
    const newName = `Updated ${Date.now()}`;

    await contactsPage.editContact({ name: newName });
    await htmx.waitForHtmxIdle();

    // Verify update
    await contactsPage.expectContactName(newName);
    await contactsPage.expectSuccessToast(/updated|saved/i);
  });

  test('edit form pre-fills existing data', async ({ htmx }) => {
    await contactsPage.htmxClick(contactsPage.editButton);

    // Verify form has existing values
    await expect(contactsPage.nameInput).not.toBeEmpty();
  });
});

test.describe('Bulk Operations', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
    await contactsPage.gotoList();
    if (!(await contactsPage.ensureHasContacts())) {
      test.skip();
      return;
    }
  });

  test('select multiple contacts enables bulk actions', async () => {
    // Select first two contacts
    await contactsPage.selectContacts([0, 1]);

    // Bulk actions should appear
    await expect(contactsPage.bulkActions).toBeVisible();
  });

  test('select all selects entire page', async () => {
    const totalCount = await contactsPage.getContactCount();
    await contactsPage.selectAllContacts();

    // Verify all checkboxes checked
    const checkedBoxes = await contactsPage.contactsTable.locator('tbody input[type="checkbox"]:checked').count();
    expect(checkedBoxes).toBe(totalCount);
  });

  test('bulk delete removes selected contacts', async ({ htmx }) => {
    const initialCount = await contactsPage.getContactCount();

    // Select and delete first contact
    await contactsPage.selectContacts([0]);
    await contactsPage.bulkDelete();
    await htmx.waitForHtmxIdle();

    // Verify count decreased
    const newCount = await contactsPage.getContactCount();
    expect(newCount).toBe(initialCount - 1);
  });
});

test.describe('Contact Detail View', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
    // Navigate to first contact
    await contactsPage.gotoList();
    const firstRow = await contactsPage.getContactData(0);
    await contactsPage.clickContact(firstRow.name);
  });

  test('displays contact header with name and type', async () => {
    await expect(contactsPage.contactHeader).toBeVisible();
    await expect(contactsPage.contactHeader.locator('.name, h1')).toBeVisible();
  });

  test('tabs switch content via HTMX', async ({ htmx }) => {
    // Switch to activity tab
    await contactsPage.switchTab('Activity');
    await htmx.waitForHtmxIdle();

    // Verify activity timeline visible
    await expect(contactsPage.activityTimeline).toBeVisible();
  });

  test('delete contact with confirmation', async ({ htmx, page }) => {
    await contactsPage.deleteContact();
    await htmx.waitForHtmxIdle();

    // Verify redirected to list
    await expect(page).toHaveURL(contactsPage.listUrl);
    await contactsPage.expectSuccessToast(/deleted/i);
  });
});
