<?php

/*
 * functions.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2009,2010 Arun Persaud
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

function DB_quote_smart($value)
{
    /* Stripslashes */
    if (get_magic_quotes_gpc()) {
        $value = stripslashes($value);
    }
    /* Quote if not a number or a numeric string */
    if (!is_numeric($value)) {
        $value = "'" . mysql_real_escape_string($value) . "'";
    }
    return $value;
}

/**************************************************
 *
 * DB - functions -- mysql backend
 *
 **************************************************/

function DB_open($DB_HOST,$DB_USER,$DB_PASSWD,$DB_DB)
{
  $version_needed = 1;

  global $db;
  if ( $db = mysql_connect($DB_HOST,$DB_USER, $DB_PASSWD))
    {
      mysql_select_db($DB_DB) or die('Error: Could not select database');	
    }
  else
    {
      echo mysql_errno() . ": " . mysql_error(). "\n";
      return -1;
    };
  
  /* check database version */
  $version = DB_get_version();
  if ($version != $version_needed)
    return -2;

  return 0;
}

function DB_query($query)
{
  /* debug/optimize the database
  $time = microtime();
  $return = mysql_query($query);
  $time = $time - microtime();

  if($time > 0.05) // this way we can find only the long ones
  {
    $logfile=fopen('/tmp/DBlog.log','a+');
    fwrite($logfile,"EXPLAIN $query ;\n");
    fwrite($logfile,"time of above query: $time\n");
    fclose($logfile);
  };

  return $return;
  */

  return mysql_query($query);
}

function DB_fetch_array($result)
{
  return mysql_fetch_array($result,MYSQL_NUM);
}

function DB_insert_id()
{
  return mysql_insert_id();
}

function DB_num_rows($result)
{
  return mysql_num_rows($result);
}
/* end Mysql functions */

function DB_query_array($query)
{
  $result = DB_query($query);
  if($result)
    {
      $return = DB_fetch_array($result);
      return $return;
    }
  
  return NULL;
}

function DB_query_array_all($query)
{
  $result = array();

  $queryresult  = DB_query($query);
  while($row = DB_fetch_array($queryresult))
    $result[] = $row;

  return $result;
}

function DB_get_version()
{
  $version = DB_query_array('SELECT version FROM Version');

  if($version)
    return $version[0];
  else
    return -1;
}

function config_check()
{
  global $DB_HOST, $DB_USER, $DB_PASSWD, $DB_DB, $DB_work;

  /* check if some variables are set in the config file, else set defaults */
  if(!isset($DB_work))
    {
      output_header();
      echo "<h1>Setup not completed</h1>";
      echo "You need to set \$DB_work in config.php. ".
	"If this is set to 1, the db-access will be suspended and one can work safely on the database.".
	"The default should be 0 for the site to work.";
      output_footer();
      exit();
    }

  if($DB_work)
    {
      output_header();
      echo "Working on the database...please check back later.";
      output_footer();
      exit();
    }

  return;
}



/****************************************************
 *
 * Output functions
 *
 ****************************************************/

function output_header()
{

  echo <<<END
<!DOCTYPE html>

<html>

<head>
  <title> Uno Statistics </title>
  <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
  <link rel="stylesheet" type="text/css" href="css/standard.css?v=2"/>	
  <script type="text/javascript" src="jquery.js"> </script>
  <script type="text/javascript" src="jquery.tablesorter.js"></script>
  <script type="text/javascript">
    $(document).ready(function()
      {
        $("#ScoreTable").tablesorter({ widgets: ['zebra']});
      });
  </script>
</head>
<body>

<header>
  <h1>The UNO database </h1>
</header>
<img class="logo" src="draw4.png" alt="Draw 4+ logo" />

END;

}

function output_footer()
{
  echo <<<END
  </div>

<footer> 
<div class="copyright"> copyright 2011 Arun Persaud </div>
<div class="source">See the latest changes via <a href="http://uno-darmstadt.git.sourceforge.net/git/gitweb.cgi?p=uno-darmstadt/uno-darmstadt;a=summary">git</a>
or download the source via
'git clone git://uno-darmstadt.git.sourceforge.net/gitroot/uno-darmstadt/uno-darmstadt'   </div> 
</footer>

</body>
</html>

END;

  return;
}

?>