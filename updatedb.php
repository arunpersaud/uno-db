<?php
/*
 * updatedb.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2010 Arun Persaud
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
$current_version = 1;

if($old_version < $current_version)
  echo "Will upgrade your database now:\n";
else
  echo "You are up to date (version ${current_version}), nothing to do.\n";

switch($old_version)
  {
  case -1:
    /* add version number */
    DB_query("CREATE table version (`version` int NOT NULL default '0')");
    DB_query("INSERT into version VALUES('1')");

    DB_query("ALTER TABLE session".
             " ADD COLUMN  `create_date` timestamp NOT NULL default '0000-00-00 00:00:00' AFTER number_of_players");

    DB_query("ALTER TABLE players".
             " ADD COLUMN  `create_date` timestamp NOT NULL default '0000-00-00 00:00:00' AFTER id");

    echo "Upgraded to version 1.\n";
  }

?>