<?php
/*
 * updatedb.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2010,2011,2012,2013 Arun Persaud
 *
 * ------------------------------------------------------------------------
 *
 * UNO-darmstadt is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * UNO-darmstadt is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see http://www.gnu.org/licenses/.  *
 *
 * ------------------------------------------------------------------------
 *
 *  wep-page:
 *     http://uno-darmstadt.sourceforge.net
 *
 *  It would be nice to get some feedback (bugs or other comments), so please drop
 *  me a line if you are using UNO-darmstadt :)
 *  have fun
 *        Arun
 */

error_reporting(E_ALL);

include_once("config.php");                /* needs to be first in list, since other includes use this */
include_once("./include/functions.php");    /* helper functions */

/* make sure that user has set all variables in config.php */
config_check();

/* open the database */
$return = DB_open($DB_HOST,$DB_USER,$DB_PASSWD,$DB_DB);
if($return<0 && $return != -2) /* -2 = wrong DB version is ok */
  exit();

/* only callable via cron or CLI */
if(isset($_SERVER['REMOTE_ADDR']))
  exit();

$old_version = DB_get_version();
$current_version = 4;

if($old_version < $current_version)
  echo "Will upgrade your database now:\n";
else
  echo "You are up to date (version ${current_version}), nothing to do.\n";

switch($old_version)
  {
  case -1:
    /* database doesn't exist, create it */
    DB_query("CREATE TABLE `games` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `session` int(11) DEFAULT NULL,".
	     "  `end_with_black_card` tinyint(1) DEFAULT NULL,".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `locations` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',".
	     "  `name` varchar(30) DEFAULT NULL,".
	     "  `coordinates` point DEFAULT NULL,".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `players` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',".
	     "  `name` varchar(30) DEFAULT NULL,".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `scores` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `game` int(11) DEFAULT NULL,".
	     "  `player` int(11) DEFAULT NULL,".
	     "  `score` int(11) DEFAULT NULL,".
	     "  `position` int(11) DEFAULT NULL,".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `session` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `date` varchar(10) DEFAULT NULL,".
	     "  `location_id` int(11) NOT NULL,".
	     "  `number_of_players` int(11) DEFAULT NULL,".
	     "  `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',".
	     "  `variation` int(11) NOT NULL DEFAULT '1',".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `variations` (".
	     "  `id` int(11) NOT NULL AUTO_INCREMENT,".
	     "  `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',".
	     "  `name` varchar(30) DEFAULT NULL,".
	     "  `short` varchar(30) DEFAULT NULL,".
	     "  PRIMARY KEY (`id`)".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("CREATE TABLE `version` (".
	     "  `version` int(11) NOT NULL DEFAULT '0'".
	     ") ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    /* add version number */
    DB_query("INSERT into version VALUES('4')");
    DB_query("INSERT into variations VALUES(NULL,NULL,'Uno default','Uno')");

    echo "Created database\n";
    break;

  case 1:
    /* add location  */
    DB_query("CREATE TABLE IF NOT EXISTS locations (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
      `name` varchar(30) DEFAULT NULL,
      `coordinates` POINT DEFAULT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    /* fill location database */
    DB_query("INSERT INTO locations select NULL,NULL,location,NULL from session group by location");

    /* modify session table to use location id*/
    DB_query("CREATE TABLE session_tmp LIKE session");
    DB_query("ALTER TABLE session_tmp CHANGE location location_id int not null");
    DB_query("ALTER TABLE session_tmp DISABLE KEYS");
    DB_query("INSERT INTO session_tmp SELECT id,date,(select id from locations where name=location),number_of_players,create_date FROM session");
    DB_query("ALTER TABLE session_tmp ENABLE KEYS");
    DB_query("RENAME TABLE session TO session_old");
    DB_query("RENAME TABLE session_tmp TO session");
    DB_query("DROP TABLE session_old");

    DB_query("UPDATE version set version=2");
    echo "Upgraded to version 2.\n";

  case 2:
    /* add table for variations */
    DB_query("CREATE TABLE IF NOT EXISTS variations (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
      `name` varchar(30) DEFAULT NULL,
      `short` varchar(30) DEFAULT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("INSERT into variations VALUES(NULL,NULL,'Uno default','Uno')");

    DB_query("ALTER TABLE session".
             " ADD COLUMN  `variation` INT(11) NOT NULL default 1 AFTER create_date");

    /* change score value for winner from -1 to -9999, since new variations might allow negative scores */
    DB_query("UPDATE scores SET score=-9999 where score=-1");

    DB_query("UPDATE version set version=3");
    echo "Upgraded to version 3.\n";

  case 3:

    /* add a backup table for the admin interface */
    DB_query("CREATE TABLE IF NOT EXISTS backup (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `create_date` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
      `content` TEXT,
      PRIMARY KEY (`id`)
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8;");

    DB_query("UPDATE version set version=4");
    echo "Upgraded to version 4.\n";


  }

?>