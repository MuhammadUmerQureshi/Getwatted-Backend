-- Companies Table
CREATE TABLE Companies (
    CompanyId INT PRIMARY KEY,
    CompanyName VARCHAR(255) NOT NULL,
    CompanyEnabled BOOLEAN,
    CompanyHomePhoto VARCHAR(255),
    CompanyBrandColour VARCHAR(50),
    CompanyBrandLogo VARCHAR(255),
    CompanyBrandFavicon VARCHAR(255),
    CompanyCreated DATETIME,
    CompanyUpdated DATETIME
);

-- SitesGroup Table
CREATE TABLE SitesGroup (
    SiteGroupId INT PRIMARY KEY,
    SiteCompanyId INT,
    SiteGroupName VARCHAR(255) NOT NULL,
    SiteGroupEnabled BOOLEAN,
    SiteGroupCreated DATETIME,
    SiteGroupUpdated DATETIME,
    FOREIGN KEY (SiteCompanyId) REFERENCES Companies(CompanyId)
);

-- Sites Table
CREATE TABLE Sites (
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
    FOREIGN KEY (SiteGroupId) REFERENCES SitesGroup(SiteGroupId)
);

-- Tariffs Table
CREATE TABLE Tariffs (
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
    FOREIGN KEY (TariffsCompanyId) REFERENCES Companies(CompanyId)
);

-- Discounts Table
CREATE TABLE Discounts (
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
    FOREIGN KEY (DiscountCompanyId) REFERENCES Companies(CompanyId)
);

-- DriversGroup Table
CREATE TABLE DriversGroup (
    DriversGroupId INT PRIMARY KEY,
    DriversGroupCompanyId INT,
    DriversGroupName VARCHAR(255) NOT NULL,
    DriversGroupEnabled BOOLEAN,
    DriversGroupDiscountId INT,
    DriverTariffId INT,
    DriversGroupCreated DATETIME,
    DriversGroupUpdated DATETIME,
    FOREIGN KEY (DriversGroupCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (DriversGroupDiscountId) REFERENCES Discounts(DiscountId),
    FOREIGN KEY (DriverTariffId) REFERENCES Tariffs(TariffsId)
);

-- Drivers Table
CREATE TABLE Drivers (
    DriverId INT PRIMARY KEY,
    DriverCompanyId INT,
    DriverEnabled BOOLEAN,
    DriverFullName VARCHAR(255) NOT NULL,
    DriverEmail VARCHAR(255),
    DriverPhone VARCHAR(50),
    DriverGroupId INT,
    DriverNotifActions BOOLEAN,
    DriverNotifPayments BOOLEAN,
    DriverNotifSystem BOOLEAN,
    DriverCreated DATETIME,
    DriverUpdated DATETIME,
    FOREIGN KEY (DriverCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (DriverGroupId) REFERENCES DriversGroup(DriversGroupId)
);

-- ChargerUsePermit Table
CREATE TABLE ChargerUsePermit (
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
CREATE TABLE PaymentMethods (
    PaymentMethodId INT PRIMARY KEY,
    PaymentMethodCompanyId INT,
    PaymentMethodName VARCHAR(255) NOT NULL,
    PaymentMethodEnabled BOOLEAN,
    PaymentMethodCreated DATETIME,
    PaymentMethodUpdated DATETIME,
    FOREIGN KEY (PaymentMethodCompanyId) REFERENCES Companies(CompanyId)
);

-- RFIDCards Table
CREATE TABLE RFIDCards (
    RFIDCardId VARCHAR(100) PRIMARY KEY,
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

-- UserRoles Table
CREATE TABLE UserRoles (
    UserRoleId INT PRIMARY KEY,
    UserRoleName VARCHAR(255) NOT NULL,
    UserRoleLevel INT,
    UserRoleCreated DATETIME,
    UserRoleUpdated DATETIME
);

-- Users Table
CREATE TABLE Users (
    UserId INT PRIMARY KEY,
    UserRoleId INT,
    UserFirstName VARCHAR(100),
    UserLastName VARCHAR(100),
    UserEmail VARCHAR(255),
    UserPhone VARCHAR(50),
    UserPaymentMethodId INT,
    UserCreated DATETIME,
    UserUpdated DATETIME,
    FOREIGN KEY (UserRoleId) REFERENCES UserRoles(UserRoleId),
    FOREIGN KEY (UserPaymentMethodId) REFERENCES PaymentMethods(PaymentMethodId)
);

-- Settings Table
CREATE TABLE Settings (
    Currency VARCHAR(10),
    TimeZone VARCHAR(50),
    DayTimeFrom TIME,
    DayTimeTo TIME,
    NightTimeFrom TIME,
    NightTimeTo TIME
);

-- Commands Table
CREATE TABLE CommandsToCharger (
    CommandId INT PRIMARY KEY,
    CommandLabel VARCHAR(255) NOT NULL,
    CommandDescription TEXT,
    CommandEnabled BOOLEAN,
    CommandParam1 VARCHAR(255),
    CommandParam2 VARCHAR(255),
    CommandParam3 VARCHAR(255),
    CommandParam4 VARCHAR(255),
    CommandParam5 VARCHAR(255)
);

-- Chargers Table
CREATE TABLE Chargers (
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
    FOREIGN KEY (ChargerPaymentMethodId) REFERENCES PaymentMethods(PaymentMethodId)
);

-- Connectors Table
CREATE TABLE Connectors (
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
CREATE TABLE ChargeSessions (
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
CREATE TABLE PaymentTransactions (
    PaymentTransactionId INT PRIMARY KEY,
    PaymentTransactionMethodUsed INT,
    PaymentTransactionDriverId INT,
    PaymentTransactionDateTime DATETIME,
    PaymentTransactionAmount DECIMAL(10,2),
    PaymentTransactionStatus VARCHAR(50),
    PaymentTransactionCompanyId INT,
    PaymentTransactionSiteId INT,
    PaymentTransactionChargerId INT,
    FOREIGN KEY (PaymentTransactionMethodUsed) REFERENCES PaymentMethods(PaymentMethodId),
    FOREIGN KEY (PaymentTransactionDriverId) REFERENCES Drivers(DriverId),
    FOREIGN KEY (PaymentTransactionCompanyId) REFERENCES Companies(CompanyId),
    FOREIGN KEY (PaymentTransactionSiteId) REFERENCES Sites(SiteId),
    FOREIGN KEY (PaymentTransactionChargerId, PaymentTransactionCompanyId, PaymentTransactionSiteId) REFERENCES Chargers(ChargerId, ChargerCompanyId, ChargerSiteId)
);

-- EventsData Table
CREATE TABLE EventsData (
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