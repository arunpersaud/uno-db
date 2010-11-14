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
  global $db;
  if ( $db = mysql_connect($DB_HOST,$DB_USER, $DB_PASSWD))
    {
      mysql_select_db($DB_DB) or die('Could not select database');	
    }
  else
    {
      die (mysql_error());
    };
}

/****************************************************
 *
 * Output functions
 *
 ****************************************************/

function output_header($type='xhtml')
{
  switch($type)
    {
    case 'xhtml':
      echo <<<END
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
     <title> Uno Statistics Admin Page</title>
     <link rel="stylesheet" type="text/css" href="css/standard001.css"/>
  </head>
<body>
END;
      break;
    case 'svg':
      header('Content-Type: text/xml; charset=iso-8859-1');
       echo <<<END
<!DOCTYPE html PUBLIC
    "-//W3C//DTD XHTML 1.1 plus MathML 2.0 plus SVG 1.1//EN"
    "http://www.w3.org/2002/04/xhtml-math-svg/xhtml-math-svg-flat.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" 
      xmlns:svg="http://www.w3.org/2000/svg" 
      xmlns:xlink="http://www.w3.org/1999/xlink">

<head>
  <title> Uno Statistics </title>
  <meta http-equiv="Content-Type" content="text/xml; charset=ISO-8859-1" />
  <link rel="stylesheet" type="text/css" href="css/standard001.css"/>	
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
END;
      break;
    }
  echo '<img class="logo" src="draw4.png" alt="Draw 4+ logo" />';
  echo '<div class="header">';
  echo '  <h1>The UNO database </h1>';
  echo '</div>';

}

?>