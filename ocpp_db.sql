-- Complete OCPP Database Schema with Authentication and Unique Constraints
-- This file creates all tables with proper relationships, unique constraints, and authentication

-- Companies Table
CREATE TABLE IF NOT EXISTS Companies (
    CompanyId INT PRIMARY KEY,
    CompanyName VARCHAR(255) NOT NULL UNIQUE, -- Globally unique company names
    CompanyEnabled BOOLEAN,
    CompanyHomePhoto VARCHAR(255),
    CompanyBrandColour VARCHAR(50),
    CompanyBrandLogo VARCHAR(255),
    CompanyBrandFavicon VARCHAR(255),
    CompanyCreated DATETIME,
    CompanyUpdated DATETIME
);

-- UserRoles Table (Authentication)
CREATE TABLE IF NOT EXISTS UserRoles (
    UserRoleId INT PRIMARY KEY,
    UserRoleName VARCHAR(255) NOT NULL UNIQUE, -- Role names should be globally unique
    UserRoleLevel INT,
    UserRoleCreated DATETIME,
    UserRoleUpdated DATETIME
);

-- Users Table (Authentication)
CREATE TABLE IF NOT EXISTS Users (
    UserId INT PRIMARY KEY,
    UserRoleId INT,
    UserFirstName VARCHAR(100),
    UserLastName VARCHAR(100),
    UserEmail VARCHAR(255) UNIQUE, -- User emails should be globally unique
    UserPhone VARCHAR(50),
    UserPaymentMethodId INT,
    UserCompanyId INT,
    UserPasswordHash VARCHAR(255), -- For authentication
    UserCreated DATETIME,
    UserUpdated DATETIME,
    FOREIGN KEY (UserRoleId) REFERENCES UserRoles(UserRoleId),
    FOREIGN KEY (UserCompanyId) REFERENCES Companies(CompanyId)
);

-- SitesGroup Table
CREATE TABLE IF NOT EXISTS SitesGroup (
    SiteGroupId INT PRIMARY KEY,
    SiteCompanyId INT,
    SiteGroupName VARCHAR(255) NOT NULL,
    SiteGroupEnabled BOOLEAN,
    SiteGroupCreated DATETIME,
    SiteGroupUpdated DATETIME,
    FOREIGN KEY (SiteCompanyId) REFERENCES Companies(CompanyId),
    -- Site group names should be unique within each company
    UNIQUE(SiteCompanyId, SiteGroupName)
);

-- Sites Table
CREATE TABLE IF NOT EXISTS Sites (
    SiteId INT PRIMARY KEY,
    SiteCompanyID INT,
    SiteEnabled BOOLEAN,
    SiteName VARCHAR(255) NOT NULL,
    SiteGroupId INT,
    SiteAddress VARCHAR(255),
    SiteCity VARCHAR(100),
    SiteRegion VARCHAR(100),
    SiteCountry VARCHAR(100),
    SiteZipCode VARCHAR(20),
    SiteGeoCoord VARCHAR(100),
    SiteTaxRate DECIMAL(5,2),
    SiteContactName VARCHAR(255),
    SiteContactPh VARCHAR(50),
    SiteContactEmail VARCHAR(255),
    SiteCreated DATETIME,
    SiteUpdated DATETIME,
    FOREIGN KEY (SiteCompanyID) REFERENCES Companies(CompanyId),
    FOREIGN KEY (SiteGroupId) REFERENCES SitesGroup(SiteGroupId),
    -- Site names must be unique within each company
    UNIQUE(SiteCompanyID, SiteName)
);

-- Tariffs Table
CREATE TABLE IF NOT EXISTS Tariffs (
    TariffsId INT PRIMARY KEY,
    TariffsCompanyId INT,
    TariffsEnabled BOOLEAN,
    TariffsName VARCHAR(255) NOT NULL,
    TariffsType VARCHAR(50),
    TariffsPer VARCHAR(50),
    TariffsRateDaytime DECIMAL(10,2),
    TariffsRateNighttime DECIMAL(10,2),
    TariffsDaytimeFrom TIME,
    TariffsDaytimeTo TIME,
    TariffsNighttimeFrom TIME,
    TariffsNighttimeTo TIME,
    TariffsFixedStartFee DECIMAL(10,2),
    TariffsIdleChargingFee DECIMAL(10,2),
    TariffsIdleApplyAfter INT,
    TariffsCreated DATETIME,
    TariffsUpdated DATETIME,
    FOREIGN KEY (TariffsCompanyId) REFERENCES Companies(CompanyId),
    -- Tariff names should be unique within each company
    UNIQUE(TariffsCompanyId, TariffsName)
);

-- Discounts Table
CREATE TABLE IF NOT EXISTS Discounts (
    DiscountId INT PRIMARY KEY,
    DiscountCompanyId INT,
    DiscountName VARCHAR(255) NOT NULL,
    DiscountEnabled BOOLEAN,
    DiscountType VARCHAR(50),
    DiscountAmount DECIMAL(10,2),
    DiscountStartDate DATE,
    DiscountEndDate DATE,
    DiscountCreated DATETIME,
    DiscountUpdated DATETIME,
    FOREIGN KEY (DiscountCompanyId) REFERENCES Companies(CompanyId),
    -- Discount names should be unique within each company
    UNIQUE(DiscountCompanyId, DiscountName)
);

-- DriversGroup Table
CREATE TABLE IF NOT EXISTS DriversGroup (
    DriversGroupId INTEGER PRIMARY KEY AUTOINCREMENT,
    DriversGroupCompanyId INT,
    DriversGroupName VARCHAR(255) NOT NULL,
    DriversGroupEnabled BOOLEAN,
    DriversGroupDiscountId INT,
    DriverTariffId INT NOT NULL,
    DriversGroupCreated DATETIME,
    DriversGroupUpdated DATETIME,
    FOREIGN KEY (DriversGroupCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (DriversGroupDiscountId) REFERENCES Discounts(DiscountId),
    FOREIGN KEY (DriverTariffId) REFERENCES Tariffs(TariffsId),
    -- Driver group names should be unique within each company
    UNIQUE(DriversGroupCompanyId, DriversGroupName)
);

-- Drivers Table
CREATE TABLE IF NOT EXISTS Drivers (
    DriverId INT PRIMARY KEY,
    DriverCompanyId INT,
    DriverEnabled BOOLEAN,
    DriverFullName VARCHAR(255) NOT NULL,
    DriverEmail VARCHAR(255),
    DriverPhone VARCHAR(50),
    DriverGroupId INT, -- Make this nullable since it will be set later
    DriverNotifActions BOOLEAN,
    DriverNotifPayments BOOLEAN,
    DriverNotifSystem BOOLEAN,
    DriverUserId INT, -- Link to Users table for authentication
    DriverCreated DATETIME,
    DriverUpdated DATETIME,
    FOREIGN KEY (DriverCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (DriverGroupId) REFERENCES DriversGroup(DriversGroupId),
    FOREIGN KEY (DriverUserId) REFERENCES Users(UserId),
    -- Driver emails should be unique within each company (if provided)
    UNIQUE(DriverCompanyId, DriverEmail)
);

-- ChargerUsePermit Table
CREATE TABLE IF NOT EXISTS ChargerUsePermit (
    ChargerUsePermitCompanyId INT,
    ChargerUsePermitSiteId INT,
    ChargerUsePermitDriverId INT,
    ChargerUsePermitEnabled BOOLEAN,
    ChargerUsePermitCreated DATETIME,
    ChargerUsePermitUpdated DATETIME,
    PRIMARY KEY (ChargerUsePermitCompanyId, ChargerUsePermitSiteId, ChargerUsePermitDriverId),
    FOREIGN KEY (ChargerUsePermitCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (ChargerUsePermitSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (ChargerUsePermitDriverId) REFERENCES Drivers(DriverId)
);

-- PaymentMethods Table
CREATE TABLE IF NOT EXISTS PaymentMethods (
    PaymentMethodId INT PRIMARY KEY,
    PaymentMethodCompanyId INT,
    PaymentMethodName VARCHAR(255) NOT NULL,
    PaymentMethodEnabled BOOLEAN,
    PaymentMethodCreated DATETIME,
    PaymentMethodUpdated DATETIME,
    FOREIGN KEY (PaymentMethodCompanyId) REFERENCES Companies(CompanyId),
    -- Payment method names should be unique within each company
    UNIQUE(PaymentMethodCompanyId, PaymentMethodName)
);

-- RFIDCards Table
CREATE TABLE IF NOT EXISTS RFIDCards (
    RFIDCardId VARCHAR(100) PRIMARY KEY, -- RFID card IDs are globally unique
    RFIDCardCompanyId INT,
    RFIDCardDriverId INT,
    RFIDCardEnabled BOOLEAN,
    RFIDCardNameOn VARCHAR(255),
    RFIDCardNumberOn VARCHAR(100),
    RFIDCardExpiration DATE,
    RFIDCardCreated DATETIME,
    RFIDCardUpdated DATETIME,
    FOREIGN KEY (RFIDCardCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (RFIDCardDriverId) REFERENCES Drivers(DriverId)
);

-- Settings Table
CREATE TABLE IF NOT EXISTS Settings (
    Currency VARCHAR(10),
    TimeZone VARCHAR(50),
    DayTimeFrom TIME,
    DayTimeTo TIME,
    NightTimeFrom TIME,
    NightTimeTo TIME
);

-- Commands Table
CREATE TABLE IF NOT EXISTS CommandsToCharger (
    CommandId INT PRIMARY KEY,
    CommandLabel VARCHAR(255) NOT NULL UNIQUE, -- Command labels should be unique
    CommandDescription TEXT,
    CommandEnabled BOOLEAN,
    CommandParam1 VARCHAR(255),
    CommandParam2 VARCHAR(255),
    CommandParam3 VARCHAR(255),
    CommandParam4 VARCHAR(255),
    CommandParam5 VARCHAR(255)
);

-- Chargers Table
CREATE TABLE IF NOT EXISTS Chargers (
    ChargerId INT,
    ChargerCompanyId INT,
    ChargerSiteId INT,
    ChargerGeoCoord VARCHAR(100),
    ChargerName VARCHAR(255) NOT NULL,
    ChargerBrand VARCHAR(100),
    ChargerModel VARCHAR(100),
    ChargerType VARCHAR(50),
    ChargerSerial VARCHAR(100),
    ChargerMeter VARCHAR(100),
    ChargerMeterSerial VARCHAR(100),
    ChargerPincode VARCHAR(20),
    ChargerWsURL VARCHAR(255),
    ChargerICCID VARCHAR(100),
    ChargerAvailability VARCHAR(50),
    ChargerIsOnline BOOLEAN,
    ChargerEnabled BOOLEAN,
    ChargerAccessType VARCHAR(50),
    ChargerActive24x7 BOOLEAN,
    ChargerMonFrom TIME,
    ChargerMonTo TIME,
    ChargerTueFrom TIME,
    ChargerTueTo TIME,
    ChargerWedFrom TIME,
    ChargerWedTo TIME,
    ChargerThuFrom TIME,
    ChargerThuTo TIME,
    ChargerFriFrom TIME,
    ChargerFriTo TIME,
    ChargerSatFrom TIME,
    ChargerSatTo TIME,
    ChargerSunFrom TIME,
    ChargerSunTo TIME,
    ChargerLastConn DATETIME,
    ChargerLastDisconn DATETIME,
    ChargerLastHeartbeat DATETIME,
    ChargerPhoto VARCHAR(255),
    ChargerFirmwareVersion VARCHAR(50),
    ChargerPaymentMethodId INT,
    ChargerCreated DATETIME,
    ChargerUpdated DATETIME,
    PRIMARY KEY (ChargerId, ChargerCompanyId, ChargerSiteId),
    FOREIGN KEY (ChargerCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (ChargerSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (ChargerPaymentMethodId) REFERENCES PaymentMethods(PaymentMethodId),
    -- Charger names must be unique within each site
    UNIQUE(ChargerCompanyId, ChargerSiteId, ChargerName),
    -- Charger serial numbers should be globally unique (if provided)
    UNIQUE(ChargerSerial)
);

-- Connectors Table
CREATE TABLE IF NOT EXISTS Connectors (
    ConnectorId INT,
    ConnectorCompanyId INT,
    ConnectorSiteId INT,
    ConnectorChargerId INT,
    ConnectorType VARCHAR(50),
    ConnectorEnabled BOOLEAN,
    ConnectorStatus VARCHAR(50),
    ConnectorMaxVolt DECIMAL(10,2),
    ConnectorMaxAmp DECIMAL(10,2),
    ConnectorCreated DATETIME,
    ConnectorUpdated DATETIME,
    PRIMARY KEY (ConnectorId, ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId),
    FOREIGN KEY (ConnectorCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (ConnectorSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (ConnectorChargerId, ConnectorCompanyId, ConnectorSiteId) REFERENCES Chargers(ChargerId, ChargerCompanyId, ChargerSiteId)
);

-- ChargeSessions Table
CREATE TABLE IF NOT EXISTS ChargeSessions (
    ChargeSessionId INT PRIMARY KEY,
    ChargerSessionCompanyId INT,
    ChargerSessionSiteId INT,
    ChargerSessionChargerId INT,
    ChargerSessionConnectorId INT,
    ChargerSessionDriverId INT,
    ChargerSessionRFIDCard VARCHAR(100),
    ChargerSessionStart DATETIME,
    ChargerSessionEnd DATETIME,
    ChargerSessionDuration INT,
    ChargerSessionReason VARCHAR(255),
    ChargerSessionStatus VARCHAR(50),
    ChargerSessionEnergyKWH DECIMAL(10,2),
    ChargerSessionPricingPlanId INT,
    ChargerSessionCost DECIMAL(10,2),
    ChargerSessionDiscountId INT,
    ChargerSessionPaymentId INT,
    ChargerSessionPaymentAmount DECIMAL(10,2),
    ChargerSessionPaymentStatus VARCHAR(50),
    ChargerSessionCreated DATETIME,
    FOREIGN KEY (ChargerSessionCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (ChargerSessionSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (ChargerSessionChargerId, ChargerSessionCompanyId, ChargerSessionSiteId) REFERENCES Chargers(ChargerId, ChargerCompanyId, ChargerSiteId),
    FOREIGN KEY (ChargerSessionConnectorId, ChargerSessionCompanyId, ChargerSessionSiteId, ChargerSessionChargerId) REFERENCES Connectors(ConnectorId, ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId),
    FOREIGN KEY (ChargerSessionDriverId) REFERENCES Drivers(DriverId),
    FOREIGN KEY (ChargerSessionRFIDCard) REFERENCES RFIDCards(RFIDCardId),
    FOREIGN KEY (ChargerSessionDiscountId) REFERENCES Discounts(DiscountId),
    FOREIGN KEY (ChargerSessionPricingPlanId) REFERENCES Tariffs(TariffsId)
);

-- PaymentTransactions Table
CREATE TABLE IF NOT EXISTS PaymentTransactions (
    PaymentTransactionId INT PRIMARY KEY,
    PaymentTransactionMethodUsed INT,
    PaymentTransactionDriverId INT,
    PaymentTransactionDateTime DATETIME,
    PaymentTransactionAmount DECIMAL(10,2),
    PaymentTransactionStatus VARCHAR(50),
    PaymentTransactionPaymentStatus VARCHAR(50) DEFAULT 'pending',
    PaymentTransactionCompanyId INT,
    PaymentTransactionSiteId INT,
    PaymentTransactionChargerId INT,
    PaymentTransactionSessionId INT,
    PaymentTransactionStripeIntentId VARCHAR(255) UNIQUE, -- Stripe intent IDs are globally unique
    PaymentTransactionCreated DATETIME,
    PaymentTransactionUpdated DATETIME,
    FOREIGN KEY (PaymentTransactionMethodUsed) REFERENCES PaymentMethods(PaymentMethodId),
    FOREIGN KEY (PaymentTransactionDriverId) REFERENCES Drivers(DriverId),
    FOREIGN KEY (PaymentTransactionCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (PaymentTransactionSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (PaymentTransactionChargerId, PaymentTransactionCompanyId, PaymentTransactionSiteId) REFERENCES Chargers(ChargerId, ChargerCompanyId, ChargerSiteId),
    FOREIGN KEY (PaymentTransactionSessionId) REFERENCES ChargeSessions(ChargeSessionId)
);

-- EventsData Table
CREATE TABLE IF NOT EXISTS EventsData (
    EventsDataNumber INT PRIMARY KEY,
    EventsDataCompanyId INT,
    EventsDataSiteId INT,
    EventsDataChargerId INT,
    EventsDataConnectorId INT,
    EventsDataSessionId INT,
    EventsDataDateTime DATETIME,
    EventsDataType VARCHAR(50),
    EventsDataTriggerReason VARCHAR(255),
    EventsDataOrigin VARCHAR(100),
    EventsDataData TEXT,
    EventsDataTemperature DECIMAL(10,2),
    EventsDataCurrent DECIMAL(10,2),
    EventsDataVoltage DECIMAL(10,2),
    EventsDataMeterValue DECIMAL(10,2),
    EventsDataCreated DATETIME,
    FOREIGN KEY (EventsDataCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (EventsDataSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (EventsDataChargerId, EventsDataCompanyId, EventsDataSiteId) REFERENCES Chargers(ChargerId, ChargerCompanyId, ChargerSiteId),
    FOREIGN KEY (EventsDataConnectorId, EventsDataCompanyId, EventsDataSiteId, EventsDataChargerId) REFERENCES Connectors(ConnectorId, ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId),
    FOREIGN KEY (EventsDataSessionId) REFERENCES ChargeSessions(ChargeSessionId)
);

-- Insert Default User Roles
INSERT OR REPLACE INTO UserRoles (UserRoleId, UserRoleName, UserRoleLevel, UserRoleCreated, UserRoleUpdated)
VALUES 
(1, 'SuperAdmin', 3, datetime('now'), datetime('now')),
(2, 'Admin', 2, datetime('now'), datetime('now')),
(3, 'Driver', 1, datetime('now'), datetime('now'));

-- Create default SuperAdmin user
-- Password is 'admin123' - CHANGE THIS IN PRODUCTION!
INSERT OR REPLACE INTO Users (
    UserId, UserRoleId, UserFirstName, UserLastName, UserEmail, 
    UserCompanyId, UserPasswordHash, UserCreated, UserUpdated
) VALUES (
    1, 
    1, -- SuperAdmin role
    'Ed', 
    'Magrassi', 
    'ed@decolight.com',  -- Changed from .local to .com
    NULL, -- SuperAdmin has no company restriction
    '$2a$12$N.tkB1o539A86O/BexEMSubiouwGWj6cCl3gsRZux5DJDIYCV7caW', -- bcrypt hash of 'admin123'
    datetime('now'),
    datetime('now')
);


-- Authentication indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON Users(UserEmail);
CREATE INDEX IF NOT EXISTS idx_users_company ON Users(UserCompanyId);
CREATE INDEX IF NOT EXISTS idx_users_role ON Users(UserRoleId);
CREATE INDEX IF NOT EXISTS idx_drivers_user ON Drivers(DriverUserId);

-- Index for company-based queries
CREATE INDEX IF NOT EXISTS idx_sites_company ON Sites(SiteCompanyID);
CREATE INDEX IF NOT EXISTS idx_chargers_company ON Chargers(ChargerCompanyId);
CREATE INDEX IF NOT EXISTS idx_drivers_company ON Drivers(DriverCompanyId);
CREATE INDEX IF NOT EXISTS idx_events_company ON EventsData(EventsDataCompanyId);
CREATE INDEX IF NOT EXISTS idx_sessions_company ON ChargeSessions(ChargerSessionCompanyId);

-- Index for site-based queries
CREATE INDEX IF NOT EXISTS idx_chargers_site ON Chargers(ChargerSiteId);
CREATE INDEX IF NOT EXISTS idx_events_site ON EventsData(EventsDataSiteId);
CREATE INDEX IF NOT EXISTS idx_sessions_site ON ChargeSessions(ChargerSessionSiteId);

-- Index for charger-based queries
CREATE INDEX IF NOT EXISTS idx_connectors_charger ON Connectors(ConnectorChargerId);
CREATE INDEX IF NOT EXISTS idx_events_charger ON EventsData(EventsDataChargerId);
CREATE INDEX IF NOT EXISTS idx_sessions_charger ON ChargeSessions(ChargerSessionChargerId);

-- Index for session-based queries
CREATE INDEX IF NOT EXISTS idx_events_session ON EventsData(EventsDataSessionId);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_session ON PaymentTransactions(PaymentTransactionSessionId);

-- Index for driver-based queries
CREATE INDEX IF NOT EXISTS idx_rfid_cards_driver ON RFIDCards(RFIDCardDriverId);
CREATE INDEX IF NOT EXISTS idx_sessions_driver ON ChargeSessions(ChargerSessionDriverId);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_driver ON PaymentTransactions(PaymentTransactionDriverId);

-- Index for RFID card queries
CREATE INDEX IF NOT EXISTS idx_sessions_rfid ON ChargeSessions(ChargerSessionRFIDCard);

-- Index for datetime-based queries (for performance on time range queries)
CREATE INDEX IF NOT EXISTS idx_events_datetime ON EventsData(EventsDataDateTime);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON ChargeSessions(ChargerSessionStart);
CREATE INDEX IF NOT EXISTS idx_sessions_end ON ChargeSessions(ChargerSessionEnd);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_datetime ON PaymentTransactions(PaymentTransactionDateTime);

-- Index for online status queries
CREATE INDEX IF NOT EXISTS idx_chargers_online ON Chargers(ChargerIsOnline);

-- Index for enabled status queries
CREATE INDEX IF NOT EXISTS idx_companies_enabled ON Companies(CompanyEnabled);
CREATE INDEX IF NOT EXISTS idx_sites_enabled ON Sites(SiteEnabled);
CREATE INDEX IF NOT EXISTS idx_chargers_enabled ON Chargers(ChargerEnabled);
CREATE INDEX IF NOT EXISTS idx_drivers_enabled ON Drivers(DriverEnabled);

-- Index for payment status queries
CREATE INDEX IF NOT EXISTS idx_sessions_payment_status ON ChargeSessions(ChargerSessionPaymentStatus);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON PaymentTransactions(PaymentTransactionStatus);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_payment_status ON PaymentTransactions(PaymentTransactionPaymentStatus);

-- Index for event type queries
CREATE INDEX IF NOT EXISTS idx_events_type ON EventsData(EventsDataType);

-- Composite indexes for common multi-column queries
CREATE INDEX IF NOT EXISTS idx_chargers_company_site ON Chargers(ChargerCompanyId, ChargerSiteId);
CREATE INDEX IF NOT EXISTS idx_connectors_company_site_charger ON Connectors(ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId);
CREATE INDEX IF NOT EXISTS idx_events_company_site_charger ON EventsData(EventsDataCompanyId, EventsDataSiteId, EventsDataChargerId);

-- Comments for documentation
-- This schema enforces the following unique constraints:
-- 1. Company names are globally unique
-- 2. Site names are unique within each company
-- 3. Charger names are unique within each site
-- 4. Site group names are unique within each company
-- 5. Driver group names are unique within each company
-- 6. Tariff names are unique within each company
-- 7. Discount names are unique within each company
-- 8. Payment method names are unique within each company
-- 9. Driver emails are unique within each company (if provided)
-- 10. User emails are globally unique
-- 11. User role names are globally unique
-- 12. Command labels are globally unique
-- 13. Charger serial numbers are globally unique (if provided)
-- 14. RFID card IDs are globally unique
-- 15. Stripe payment intent IDs are globally unique

-- Authentication Features:
-- - Role-based access control with SuperAdmin, Admin, Driver roles
-- - User-to-driver linking for driver authentication
-- - Password hashing support with bcrypt
-- - Company-based user isolation
-- - Default test users with hashed passwords

-- Default Users Created:
-- 1. SuperAdmin: admin@ocpp.com / admin123
-- 2. Company Admin: admin@testcompany.com / admin123
-- 3. Driver: driver@testcompany.com / driver123

-- SECURITY WARNING: Change all default passwords in production!