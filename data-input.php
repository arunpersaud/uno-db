<?php
/*
 * data-input.php --  this is part of a web interface for UNO-darmstadt
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

include('config.php');
include('include/functions.php');

output_header();
/*
 * open database 
 */
if( $db = mysql_connect($DB_HOST,$DB_USER, $DB_PASSWD) )
  {
    mysql_select_db($DB_DB) or die('Could not select database');	
  }
 else
   die (mysql_error());

/* check if file is present */
if(!$_REQUEST["file"])
  {	
    /* output names and dates for cut and paste */
    echo "<div>At the moment the file format is not very forgiving, so you can't make any syntax mistakes. </div>\n";
    echo "<div class=\"cutandpaste\">\n";
    echo "<h3> Cut & Paste section </h3>\n";
    
    echo "<div class=\"places\">\n";
    $datatmp = mysql_query("SELECT DISTINCT location FROM session ORDER BY location");
    while($who = mysql_fetch_array($datatmp, MYSQL_NUM))
      echo "<span>".$who[0]."</span>\n";
    echo "</div>\n";
    
    echo "<div class=\"allnames\">\n";
    $datatmp = mysql_query("SELECT name FROM players ORDER BY name");
    while($who = mysql_fetch_array($datatmp, MYSQL_NUM))
      echo "<span>".$who[0]."</span>\n";
    echo "</div>\n";
    
    echo "<div class=\"dates\">\n";
    echo "<span>".date("Y-m-d",time()-60*60*24*4)."</span>\n";
    echo "<span>".date("Y-m-d",time()-60*60*24*3)."</span>\n";
    echo "<span>".date("Y-m-d",time()-60*60*24*2)."</span>\n";
    echo "<span>".date("Y-m-d",time()-60*60*24*1)."</span>\n";
    echo "<span>".date("Y-m-d",time())."</span>";
    echo "</div>\n";
    
    echo "</div>\n";
    
    
    /* output form for PGN files */
    echo "<div class=\"PGNinput\">\n";
    echo "<form action=\"data-input.php\">
<fieldset>
<legend>PGN</legend>
<textarea name=\"file\" cols=\"70\" rows=\"30\">
[Site \"\"]
[Date \"\"]
[Players \"\"]
[Result \"\"]
[Games \"\"]
</textarea>
<input type=\"submit\" name=\"submit\" value=\"check\">
</fieldset>
</form>\n";
    echo "<p> use date format yyyy-mm-dd. Don't end game with a new line</p>\n</div>";
  }
 else if($_REQUEST["file"])
   {
     if(isset($_REQUEST['submit']) && $_REQUEST['submit']=='check' )
       {
	 /* got data, try to do some verifications, show data to user and wait for submit */
	 
	 $file=$_REQUEST["file"];
	 /*  if ($file == "rebuild")
	  {
	  echo "will rebuild the data base <br>";
	  sqlite_query($db, "CREATE TABLE session (id INTEGER PRIMARY KEY, date VARCHAR(10), location VARCHAR(15), number_of_players INTEGER)");
	  sqlite_query($db, "CREATE TABLE players (id INTEGER PRIMARY KEY, name VARCHAR(30))");
	  sqlite_query($db, "CREATE TABLE games   (id INTEGER PRIMARY KEY, session INTEGER,  end_with_black_card BOOLEAN)");
	  sqlite_query($db, "CREATE TABLE scores  (id INTEGER PRIMARY KEY, game INTEGER, player INTEGER, score INTEGER, position INTEGER)");
	  
	  //      $lines = file("all.txt");
	  }
	  else 
	 */
	 $lines = explode("\n",$file);
	 
	 echo "checking syntax<br>";
	 
	 /* some variables used to store information which we get while parsing */
	 $inheader  = 1;        /* where are we, do we need to start looking for scores or are we still in the header*/ 
	 $names     = array();  /* the names of the players playing in that session*/
	 $oldpoints = array();  /* the total score of the last game, so that we can store only the points made in that single game*/
	 
	 foreach($lines as $line)
	   {
	     /* did we found a new header? */
	     if( ($inheader==0) and ereg("^[[:space:]]*\[.*$",$line) )
	       $inheader = 1;
	     
	     /* parse header */
	     if($inheader)
	       {
		 ereg("^\s*\[\s*[sS]ite[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$site);
		 ereg("^\s*\[\s*[dD]ate[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$date);
		 ereg("^\s*\[\s*[pP]layers[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$players);
		 ereg("^\s*\[\s*[rR]esult[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$result);
		 ereg("^\s*\[\s*[gG]ames[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$n);
		 
		 if( ereg("^[[:space:]]*[^[].*$",$line) and ($inheader==1) )
		   {
		     /*this is the end of the header, prepare to store game in database...*/
		     $players = explode(" ",trim($players[1]));
		     $N       = sizeof($players);
		     echo "found $N players<br>";
		     
		     /*add a new entry for this session of games */
		     echo "will get a new session id for: ",$date[1]," ",$site[1]," ",$N,"<br />\n";
	     
		     /* check for new names and remember player ids*/
		     foreach($players as $player) 
		       {
			 $qresult=mysql_query("SELECT id FROM players WHERE name='$player'");
			 if(mysql_num_rows($qresult))
			   {
			     /* this player already exists in the database */
			     $playerid = mysql_fetch_array($qresult, MYSQL_NUM);
			     $names[]  = array("name"=>$player,"id" => $playerid[0]);
			     echo "found old player $player (id=".$playerid[0].") <br>";
			   }
			 else
			   {
			     /* found a new player */
			     $names[]     = array("name"=>$player,"id" => 0);
			     echo "new player $player  <br>";
			   }
		       }
		     /* initialize the $oldpoints variable */
		     for($i=0; $i<$N; $i++)
		       $oldpoints[$i] = 0;
		     
		     /* we now have all the names and the session id.
		      * Therefore we are finished parsing the header and can start adding single game infos
		      */
		     
		     $inheader = 0;
		   }
	       }
	     else 
	       {
		 /* parse points */
		 $points = preg_split ("/[\s]+/",trim($line));
		 $ewbc=0; /* ewbc = end with black card */
		 
		 if(sizeof($points)>$N)
		   $ewbc=1;
		 if(sizeof($points)<$N)
		   {
		     echo "found an error in the file... need to repair this manual at the moment...\n";	
		     echo sizeof($points)." -- $N";
		     continue;
		   };
		 
		 /* store this game */
		 echo "will store scores of a game";
		 if($ewbc) " ending with a black card";
		 echo ": <br />\n";

		 for($i=0; $i<$N; $i++)
		   {
		     if(trim($points[$i]) != "-")
		       {
			 $p = $points[$i] - $oldpoints[$i];
			 $oldpoints[$i] = $points[$i];
			 if($p<0) echo "points <0 detected at gamesid $gamesid";
		       }
		     else
		       {
			 $p = -1; /* for the winner of that round*/
		       };
		     /* get player id */
		     $result=mysql_query("SELECT id FROM players WHERE name='".$players[$i]."'");
		     $playerid = mysql_fetch_array($result,MYSQL_NUM);
		     if($playerid)
		       $player_id = $playerid[0];
		     else
		       $player_id = "new";
		     echo "player=", $player_id," point=", $p," position:", $i,"<br />\n";

		   };
	       }; /* end inheader if */
	   }; /* end for loop over input lines */

	 echo "<div class=\"PGNinput\">\n";
	 echo "<form action=\"data-input.php\">
<fieldset>
<legend>PGN</legend>
<textarea name=\"file\" cols=\"70\" rows=\"30\">
$file</textarea>
<input type=\"submit\" name=\"submit\" value=\"check\">
<input type=\"submit\" name=\"submit\" value=\"submit\">
</fieldset>
</form>\n";
	 echo "<p> use date format yyyy-mm-dd. Don't end game with a new line</p>\n</div>";
       }
     else  if(isset($_REQUEST['submit']) && $_REQUEST['submit']=='submit')
       {
	 /* got data, try to do some verifications, show data to user and wait for submit */
	 
	 $file=$_REQUEST["file"];
	 /*  if ($file == "rebuild")
	  {
	  echo "will rebuild the data base <br>";
	  sqlite_query($db, "CREATE TABLE session (id INTEGER PRIMARY KEY, date VARCHAR(10), location VARCHAR(15), number_of_players INTEGER)");
	  sqlite_query($db, "CREATE TABLE players (id INTEGER PRIMARY KEY, name VARCHAR(30))");
	  sqlite_query($db, "CREATE TABLE games   (id INTEGER PRIMARY KEY, session INTEGER,  end_with_black_card BOOLEAN)");
	  sqlite_query($db, "CREATE TABLE scores  (id INTEGER PRIMARY KEY, game INTEGER, player INTEGER, score INTEGER, position INTEGER)");
	  
	  //      $lines = file("all.txt");
	  }
	  else 
	 */
	 $lines = explode("\n",$file);
	 
	 echo "adding file to database <br>";
	 
	 /* some variables used to store information which we get while parsing */
	 $inheader  = 1;        /* where are we, do we need to start looking for scores or are we still in the header*/ 
	 $names     = array();  /* the names of the players playing in that session*/
	 $oldpoints = array();  /* the total score of the last game, so that we can store only the points made in that single game*/
	 
	 foreach($lines as $line)
	   {
	     /* did we found a new header? */
	     if( ($inheader==0) and ereg("^[[:space:]]*\[.*$",$line) )
	       $inheader = 1;
	     
	     /* parse header */
	     if($inheader)
	       {
		 ereg("^\s*\[\s*[sS]ite[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$site);
		 ereg("^\s*\[\s*[dD]ate[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$date);
		 ereg("^\s*\[\s*[pP]layers[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$players);
		 ereg("^\s*\[\s*[rR]esult[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$result);
		 ereg("^\s*\[\s*[gG]ames[[:space:]]*\"(.*)\"\s*\][[:space:]]*$",$line,$n);
		 
		 if( ereg("^[[:space:]]*[^[].*$",$line) and ($inheader==1) )
		   {
		     /*this is the end of the header, prepare to store game in database...*/
		     $players = explode(" ",trim($players[1]));
		     $N       = sizeof($players);
		     echo "found $N players<br>";
		     
		     /*add a new entry for this session of games */
		     mysql_query("INSERT INTO session VALUES (NULL, '$date[1]','$site[1]',$N)");
		     $session_id = mysql_insert_id();
		     
		     /* check for new names and remember player ids*/
		     foreach($players as $player) 
		       {
			 $qresult=mysql_query("SELECT id FROM players WHERE name='$player'");
			 if(mysql_num_rows($qresult))
			   {
			     /* this player already exists in the database */
			     $playerid = mysql_fetch_array($qresult, MYSQL_NUM);
			     $names[]  = array("name"=>$player,"id" => $playerid[0]);
			     echo "found old player $player (id=".$playerid[0].") <br>";
			   }
			 else
			   {
			     /* found a new player */
			     mysql_query("INSERT INTO players VALUES (NULL, '$player')");
			     $playerid[0] = mysql_insert_id();
			     $names[]     = array("name"=>$player,"id" => $playerid[0]);
			     echo "new player $player ".$playerid[0]." <br>";
			   }
		       }
		     /* initialize the $oldpoints variable */
		     for($i=0; $i<$N; $i++)
		       $oldpoints[$i] = 0;
		     
		     /* we now have all the names and the session id.
		      * Therefore we are finished parsing the header and can start adding single game infos
		      */
		     
		     $inheader = 0;
		   }
	       }
	     else 
	       {
		 /* parse points */
		 $points = preg_split ("/[\s]+/",trim($line));
		 $ewbc=0; /* ewbc = end with black card */
		 
		 if(sizeof($points)>$N)
		   $ewbc=1;
		 if(sizeof($points)<$N)
		   {
		     echo "found an error in the file... need to repair this manual at the moment...\n";	
		     echo sizeof($points)." -- $N";
		     continue;
		   };
		 
		 /* store this game */
		 mysql_query("INSERT INTO games VALUES (NULL, '$session_id', '$ewbc')");
		 $gamesid = mysql_insert_id();    
		 
		 for($i=0; $i<$N; $i++)
		   {
		     if(trim($points[$i]) != "-")
		       {
			 $p = $points[$i] - $oldpoints[$i];
			 $oldpoints[$i] = $points[$i];
			 if($p<0) echo "points <0 detected at gamesid $gamesid";
		       }
		     else
		       {
			 $p = -1; /* for the winner of that round*/
		       };
		     /* get player id */
		     $result=mysql_query("SELECT id FROM players WHERE name='".$players[$i]."'");
		     $playerid = mysql_fetch_array($result,MYSQL_NUM);
		     $player_id = $playerid[0];
		     mysql_query("INSERT INTO scores VALUES (NULL, '$gamesid', '$player_id', '$p', '$i')");
		   };
	       }; /* end inheader if */
	   }; /* end for loop over input lines */
       }; /* end if submit button */
   } /* end input data present */


mysql_close($db); 
?>
       
       <div class="footer">
<p>Back to the <a href="./index.php">UNO page</a> or restart the <a href="data-input.php">admin page</a></p>
</div>
</body>
</html>

