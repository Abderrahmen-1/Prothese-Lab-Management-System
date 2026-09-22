/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-12.2.2-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: labo_web
-- ------------------------------------------------------
-- Server version	12.2.2-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `dentist_history`
--

DROP TABLE IF EXISTS `dentist_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `dentist_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dentistname` varchar(50) DEFAULT NULL,
  `pNumber` varchar(50) DEFAULT NULL,
  `pFirstname` varchar(50) DEFAULT NULL,
  `pLastname` varchar(50) DEFAULT NULL,
  `pKhedma` varchar(50) DEFAULT NULL,
  `pDate` date DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dentist_history`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `dentist_history` WRITE;
/*!40000 ALTER TABLE `dentist_history` DISABLE KEYS */;
INSERT INTO `dentist_history` VALUES
(1,'dadi','0770024595','hakim','khelfouni','partiel haut','2026-06-13',3),
(2,'saad','0664291075','del3o','khelfouni','flexible haut et bas','2026-04-12',3);
/*!40000 ALTER TABLE `dentist_history` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `dentist_registry`
--

DROP TABLE IF EXISTS `dentist_registry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `dentist_registry` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `dentist_name` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`dentist_name`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dentist_registry`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `dentist_registry` WRITE;
/*!40000 ALTER TABLE `dentist_registry` DISABLE KEYS */;
INSERT INTO `dentist_registry` VALUES
(1,3,'dadi'),
(2,3,'saad');
/*!40000 ALTER TABLE `dentist_registry` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `dentist_stat`
--

DROP TABLE IF EXISTS `dentist_stat`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `dentist_stat` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dentist_name` varchar(50) NOT NULL,
  `total_khedma` int(11) DEFAULT 0,
  `khalsin` decimal(10,2) DEFAULT 0.00,
  `machi_khalsin` decimal(10,2) DEFAULT 0.00,
  `month` int(11) DEFAULT NULL,
  `year` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dentist_stat`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `dentist_stat` WRITE;
/*!40000 ALTER TABLE `dentist_stat` DISABLE KEYS */;
INSERT INTO `dentist_stat` VALUES
(1,'dadi',1,0.00,20000.00,6,2026,3),
(2,'saad',1,0.00,25000.00,4,2026,3);
/*!40000 ALTER TABLE `dentist_stat` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `dentists`
--

DROP TABLE IF EXISTS `dentists`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `dentists` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `dentist_name` varchar(50) NOT NULL,
  `patient_firstname` varchar(50) DEFAULT NULL,
  `patient_lastname` varchar(50) DEFAULT NULL,
  `patient_number` varchar(20) DEFAULT NULL,
  `Dkhedma` varchar(50) DEFAULT NULL,
  `price` float DEFAULT NULL,
  `finished` varchar(10) DEFAULT NULL,
  `khalsa` varchar(10) DEFAULT NULL,
  `date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dentists`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `dentists` WRITE;
/*!40000 ALTER TABLE `dentists` DISABLE KEYS */;
INSERT INTO `dentists` VALUES
(1,3,'dadi','hakim','khelfouni','0770024595','partiel haut',20000,'no','yes','2026-06-13');
/*!40000 ALTER TABLE `dentists` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `khedma`
--

DROP TABLE IF EXISTS `khedma`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `khedma` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `khedman` varchar(50) DEFAULT NULL,
  `khedma_price` float DEFAULT NULL,
  `khedma_date` date DEFAULT NULL,
  `khedma_dentist` varchar(50) DEFAULT NULL,
  `khedma_patient` varchar(50) DEFAULT NULL,
  `khedma_wajda` varchar(20) NOT NULL,
  `khedma_khalsa` varchar(20) DEFAULT 'no',
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `khedma`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `khedma` WRITE;
/*!40000 ALTER TABLE `khedma` DISABLE KEYS */;
INSERT INTO `khedma` VALUES
(1,'flexible haut et bas',40000,'2026-03-15','NO','0660999242','no','yes',3),
(2,'partiel haut',15000,'2026-04-12','NO','0666666666','no','no',3),
(3,'partiel haut',15000,'2026-03-14','NO','0611111111','no','no',3),
(4,'partiel haut',20000,'2026-06-13','Dr.dadi','0770024595','no','yes',3),
(6,'partiel haut',20000,'2026-03-15','NO','0788888888','no','no',3);
/*!40000 ALTER TABLE `khedma` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `other_prothesists`
--

DROP TABLE IF EXISTS `other_prothesists`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `other_prothesists` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `pName` varchar(50) NOT NULL,
  `pNumber` varchar(50) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`pNumber`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `other_prothesists`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `other_prothesists` WRITE;
/*!40000 ALTER TABLE `other_prothesists` DISABLE KEYS */;
INSERT INTO `other_prothesists` VALUES
(1,'mohamed','11223344',3),
(2,'mouloud','55667788',3);
/*!40000 ALTER TABLE `other_prothesists` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `other_prothesists_khedma`
--

DROP TABLE IF EXISTS `other_prothesists_khedma`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `other_prothesists_khedma` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `patient_number` varchar(50) DEFAULT NULL,
  `dentist_name` varchar(50) DEFAULT NULL,
  `pName` varchar(50) NOT NULL,
  `pNumber` varchar(50) NOT NULL,
  `pDate` date DEFAULT NULL,
  `pKhedma` varchar(50) DEFAULT NULL,
  `pPrice` decimal(10,2) DEFAULT NULL,
  `pVersa` varchar(20) DEFAULT NULL,
  `pB9aw` varchar(20) DEFAULT NULL,
  `pKhalsa` varchar(20) DEFAULT NULL,
  `pFinished` varchar(20) DEFAULT 'no',
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `other_prothesists_khedma`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `other_prothesists_khedma` WRITE;
/*!40000 ALTER TABLE `other_prothesists_khedma` DISABLE KEYS */;
INSERT INTO `other_prothesists_khedma` VALUES
(1,'0660999242',NULL,'mohamed','11223344','2026-03-17','flexible haut et bas',10000.00,'5000.0','0','yes','no',3),
(2,'0611111111',NULL,'mouloud','55667788','2026-03-15','partiel haut',8000.00,'3000.0','5000.0','no','no',3),
(3,'0770024595','dadi','mohamed','11223344','2026-06-13','partiel haut',8000.00,'8000','0','yes','no',3),
(4,'0664291075','saad','mohamed','11223344','2026-04-12','flexible haut et bas',8000.00,'8000','0','yes','yes',3),
(5,'0788888888',NULL,'mohamed','11223344','2026-03-17','partiel haut',8000.00,'5000.0','3000.0','no','no',3);
/*!40000 ALTER TABLE `other_prothesists_khedma` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `patient`
--

DROP TABLE IF EXISTS `patient`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `patient` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `patient_firstname` varchar(50) NOT NULL,
  `patient_lastname` varchar(50) NOT NULL,
  `patient_number` varchar(20) DEFAULT NULL,
  `T_ype` varchar(20) DEFAULT NULL,
  `la_date` date DEFAULT NULL,
  `finished` varchar(20) DEFAULT NULL,
  `khalsa` varchar(20) DEFAULT NULL,
  `versa` int(11) DEFAULT NULL,
  `b9aw` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `patient_number` (`patient_number`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `patient`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `patient` WRITE;
/*!40000 ALTER TABLE `patient` DISABLE KEYS */;
INSERT INTO `patient` VALUES
(1,3,'abderrahmen','khelfouni','0660999242','flexible haut et bas','2026-03-15','no','no',15000,25000),
(2,3,'mehdi','khelfouni','0666666666','partiel haut','2026-04-12','no','no',5000,10000),
(3,3,'malek','khelfouni','0611111111','partiel haut','2026-03-14','no','no',7500,7500),
(4,3,'hichame','khelfouni','0788888888','partiel haut','2026-03-15','no','no',7500,12500);
/*!40000 ALTER TABLE `patient` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `patient_history`
--

DROP TABLE IF EXISTS `patient_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `patient_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `firstname` varchar(50) DEFAULT NULL,
  `lastname` varchar(50) DEFAULT NULL,
  `pNumber` varchar(50) DEFAULT NULL,
  `pDate` date DEFAULT NULL,
  `pKhedma` varchar(50) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `pNumber` (`pNumber`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `patient_history`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `patient_history` WRITE;
/*!40000 ALTER TABLE `patient_history` DISABLE KEYS */;
INSERT INTO `patient_history` VALUES
(1,'abderrahmen','khelfouni','0660999242','2026-03-15','flexible haut et bas',3),
(2,'mehdi','khelfouni','0666666666','2026-04-12','partiel haut',3),
(3,'malek','khelfouni','0611111111','2026-03-14','partiel haut',3),
(4,'hichame','khelfouni','0788888888','2026-03-15','partiel haut',3);
/*!40000 ALTER TABLE `patient_history` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `patient_stat`
--

DROP TABLE IF EXISTS `patient_stat`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `patient_stat` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `patients_number` int(11) DEFAULT 0,
  `khalsin` decimal(10,2) DEFAULT NULL,
  `machi_khalsin` decimal(10,2) DEFAULT NULL,
  `month` int(11) DEFAULT NULL,
  `year` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `patient_stat`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `patient_stat` WRITE;
/*!40000 ALTER TABLE `patient_stat` DISABLE KEYS */;
INSERT INTO `patient_stat` VALUES
(1,3,30000.00,45000.00,3,2026,3),
(2,1,5000.00,10000.00,4,2026,3);
/*!40000 ALTER TABLE `patient_stat` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `prothesist_stat`
--

DROP TABLE IF EXISTS `prothesist_stat`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `prothesist_stat` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `prothesist_name` varchar(50) NOT NULL,
  `prothesist_number` varchar(50) NOT NULL,
  `total_khedma` int(11) DEFAULT 0,
  `khalsin` decimal(10,2) DEFAULT 0.00,
  `machi_khalsin` decimal(10,2) DEFAULT 0.00,
  `month` int(11) DEFAULT NULL,
  `year` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `prothesist_stat`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `prothesist_stat` WRITE;
/*!40000 ALTER TABLE `prothesist_stat` DISABLE KEYS */;
INSERT INTO `prothesist_stat` VALUES
(1,'mohamed','11223344',2,15000.00,3000.00,3,2026,3),
(2,'mouloud','55667788',1,3000.00,5000.00,3,2026,3),
(3,'mohamed','11223344',1,3000.00,5000.00,6,2026,3),
(4,'mohamed','11223344',1,8000.00,0.00,4,2026,3);
/*!40000 ALTER TABLE `prothesist_stat` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `sel3a`
--

DROP TABLE IF EXISTS `sel3a`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sel3a` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `sel3a_name` varchar(50) NOT NULL,
  `sel3a_price` float NOT NULL,
  `buy_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sel3a`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `sel3a` WRITE;
/*!40000 ALTER TABLE `sel3a` DISABLE KEYS */;
INSERT INTO `sel3a` VALUES
(1,3,'dents',2000,'2026-03-14'),
(2,3,'la sire',4500,'2026-03-15');
/*!40000 ALTER TABLE `sel3a` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_name` varchar(50) NOT NULL,
  `user_password` varchar(500) NOT NULL,
  `user_email` varchar(50) NOT NULL,
  `user_phoneNumber` varchar(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_email` (`user_email`),
  UNIQUE KEY `user_phoneNumber` (`user_phoneNumber`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES
(1,'mehdi','scrypt:32768:8:1$gj8X3coxl8QtnfYG$2145ab16d0857c5b0bd7bdd9e51120edddbe63957cb639b8606786896f8dbb6d46dd1e96e85f4ba417bd2f65d89266dd6bcc20e474da1228a4127b46ce2da845','mehdi@gmail.com','0699965247'),
(3,'abderrahmen','scrypt:32768:8:1$RpgiZK2QliQqY2Uz$12e3546ccb6e1a524201cfe062a0e5f8d61f5b4c09a9d967b410b5b440abaeaba62ad6b6b828f267b6768ec0cb0579e1069c126ddeaa10a195e22f16427f48e4','abderrahmen@gmail.com','0660999242');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-03-30 19:59:44
